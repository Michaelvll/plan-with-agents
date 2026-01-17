# Final Agreed Design

**Task:** Design a WebSocket notification service

**Status:** debating

---

## Design

# WebSocket Notification Service

## Architecture Overview

A horizontally scalable, stateful WebSocket notification service with strong delivery guarantees, comprehensive failure recovery, and production-grade observability.

```
┌─────────────────────────────────────────────────────────────┐
│              Load Balancer (Layer 4 / Layer 7)              │
│          Consistent Hash on user_id with fallback           │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────┴────────────┐
       │                        │
┌──────▼──────┐          ┌──────▼──────┐
│ WS Server 1 │          │ WS Server 2 │
│ (Node.js)   │          │ (Node.js)   │
└──────┬──────┘          └──────┬──────┘
       │                        │
       └────────────┬───────────┘
                    │
       ┌────────────▼────────────┐
       │   Redis Cluster         │
       │   - PubSub channels     │
       │   - Connection registry │
       │   - Sequence numbers    │
       └────────────┬────────────┘
                    │
       ┌────────────▼────────────┐
       │   PostgreSQL            │
       │   - Notification store  │
       │   - Delivery tracking   │
       │   - User preferences    │
       └─────────────────────────┘
```

## Core Components

### 1. WebSocket Server

```typescript
// server.ts
import WebSocket from 'ws';
import { createServer } from 'http';
import { RedisClient } from './redis-client';
import { NotificationStore } from './notification-store';
import { AuthService } from './auth-service';
import { RateLimiter } from './rate-limiter';
import { MetricsCollector } from './metrics';

interface ServerConfig {
  port: number;
  redisUrl: string;
  postgresUrl: string;
  heartbeatInterval: number;
  maxConnectionsPerUser: number;
  maxMessageSize: number;
  messageRateLimit: number;
  gracefulShutdownTimeout: number;
  enableMessageOrdering: boolean; // NEW: configurable ordering
  offlineRetentionDays: number; // NEW: how long to keep offline notifications
}

class NotificationServer {
  private wss: WebSocket.Server;
  private redis: RedisClient;
  private store: NotificationStore;
  private auth: AuthService;
  private rateLimiter: RateLimiter;
  private metrics: MetricsCollector;
  private connections: Map<string, Set<WebSocket>>;
  private isShuttingDown: boolean = false;
  private config: ServerConfig;
  private serverId: string;
  private messageOrdering: MessageOrderingService | null;

  constructor(config: ServerConfig) {
    this.config = config;
    this.serverId = `${process.env.HOSTNAME || 'server'}-${process.pid}`;
    this.connections = new Map();
    this.redis = new RedisClient(config.redisUrl);
    this.store = new NotificationStore(config.postgresUrl);
    this.auth = new AuthService();
    this.rateLimiter = new RateLimiter(config.messageRateLimit);
    this.metrics = new MetricsCollector();
    this.messageOrdering = config.enableMessageOrdering 
      ? new MessageOrderingService(this.redis)
      : null;
    
    const server = createServer();
    this.wss = new WebSocket.Server({ 
      server,
      verifyClient: this.verifyClient.bind(this),
      maxPayload: config.maxMessageSize
    });
    
    server.listen(config.port);
    this.setupEventHandlers();
    this.startHeartbeat(config.heartbeatInterval);
    this.setupGracefulShutdown();
    this.startBackgroundJobs();
  }

  private async verifyClient(
    info: { origin: string; req: IncomingMessage },
    callback: (result: boolean, code?: number, message?: string) => void
  ): Promise<void> {
    try {
      if (this.isShuttingDown) {
        callback(false, 503, 'Server shutting down');
        return;
      }

      const token = this.extractToken(info.req);
      if (!token) {
        callback(false, 401, 'Missing authentication token');
        return;
      }

      const user = await this.auth.validateToken(token);
      if (!user) {
        callback(false, 401, 'Invalid or expired token');
        return;
      }
      
      // Check connection limit per user
      const userConnections = await this.redis.getUserConnectionCount(user.id);
      if (userConnections >= this.config.maxConnectionsPerUser) {
        // NEW: Allow explicit disconnect of oldest connection if requested
        const forceReconnect = info.req.headers['x-force-reconnect'] === 'true';
        if (forceReconnect) {
          await this.disconnectOldestConnection(user.id);
        } else {
          callback(false, 429, 'Connection limit exceeded');
          return;
        }
      }
      
      (info.req as any).user = user;
      callback(true);
    } catch (error) {
      console.error('Error in verifyClient:', error);
      this.metrics.recordError('verify_client', error);
      callback(false, 500, 'Authentication service unavailable');
    }
  }

  private setupEventHandlers(): void {
    this.wss.on('connection', this.handleConnection.bind(this));
    
    // Subscribe to notification channel
    this.redis.subscribe('notifications', this.handleNotification.bind(this));
    
    // NEW: Subscribe to cross-server commands
    this.redis.subscribe('server:commands', this.handleServerCommand.bind(this));
    
    this.wss.on('error', (error) => {
      console.error('WebSocket server error:', error);
      this.metrics.recordError('server', error);
    });
  }

  private async handleConnection(ws: WebSocket, req: IncomingMessage): Promise<void> {
    const user = (req as any).user;
    const connectionId = this.generateConnectionId();
    
    try {
      // Get last seen sequence for this user (for ordering)
      const lastSeq = this.messageOrdering 
        ? await this.messageOrdering.getLastSeenSequence(user.id)
        : null;

      // Store connection metadata
      await this.store.addConnection({
        connectionId,
        userId: user.id,
        serverId: this.serverId,
        connectedAt: new Date(),
        lastSeenSequence: lastSeq || 0,
        metadata: {
          userAgent: req.headers['user-agent'],
          ip: this.extractClientIp(req),
          protocol: req.headers['sec-websocket-protocol']
        }
      });

      // Register in Redis for cross-server routing
      await this.redis.addUserConnection(user.id, connectionId, this.serverId);

      // Add to in-memory map
      if (!this.connections.has(user.id)) {
        this.connections.set(user.id, new Set());
      }
      this.connections.get(user.id)!.add(ws);

      // Attach metadata
      (ws as any).userId = user.id;
      (ws as any).connectionId = connectionId;
      (ws as any).isAlive = true;
      (ws as any).connectedAt = Date.now();
      (ws as any).lastSeenSequence = lastSeq || 0;

      // Event handlers
      ws.on('pong', () => {
        (ws as any).isAlive = true;
      });

      ws.on('message', async (data: Buffer) => {
        try {
          await this.handleMessage(ws, user.id, data.toString('utf8'));
        } catch (error) {
          console.error(`Error handling message from user ${user.id}:`, error);
          this.metrics.recordError('message_handling', error);
        }
      });

      ws.on('close', async (code: number, reason: Buffer) => {
        await this.handleDisconnection(ws, user.id, connectionId);
        this.metrics.recordDisconnection(code, reason.toString());
      });

      ws.on('error', (error) => {
        console.error(`WebSocket error for user ${user.id}:`, error);
        this.metrics.recordError('websocket', error);
      });

      // Send connection acknowledgment
      this.sendMessage(ws, {
        type: 'connected',
        connectionId,
        serverId: this.serverId,
        timestamp: Date.now(),
        lastSeenSequence: lastSeq || 0,
        capabilities: {
          maxMessageSize: this.config.maxMessageSize,
          heartbeatInterval: this.config.heartbeatInterval,
          messageOrdering: this.config.enableMessageOrdering,
          supportedFeatures: ['subscriptions', 'priorities', 'acknowledgments', 'ordering']
        }
      });

      // NEW: Deliver missed notifications with optional ordering
      await this.deliverMissedNotifications(ws, user.id, lastSeq || 0);

      this.metrics.recordConnection(user.id);
    } catch (error) {
      console.error('Error during connection setup:', error);
      this.metrics.recordError('connection_setup', error);
      ws.close(1011, 'Internal server error');
    }
  }

  private async handleDisconnection(
    ws: WebSocket,
    userId: string,
    connectionId: string
  ): Promise<void> {
    try {
      // Update last seen sequence before disconnecting
      if (this.messageOrdering) {
        const lastSeq = (ws as any).lastSeenSequence;
        await this.messageOrdering.updateLastSeenSequence(userId, lastSeq);
      }

      // Remove from in-memory map
      const userConnections = this.connections.get(userId);
      if (userConnections) {
        userConnections.delete(ws);
        if (userConnections.size === 0) {
          this.connections.delete(userId);
        }
      }

      // Remove from Redis
      await this.redis.removeUserConnection(userId, connectionId);

      // Archive connection record (soft delete for audit trail)
      await this.store.archiveConnection(connectionId);

      // Record session metrics
      const duration = Date.now() - (ws as any).connectedAt;
      this.metrics.recordSessionDuration(userId, duration);
    } catch (error) {
      console.error('Error during disconnection cleanup:', error);
      this.metrics.recordError('disconnection', error);
    }
  }

  private async handleNotification(message: string): Promise<void> {
    try {
      const notification = JSON.parse(message) as Notification;
      
      // Check expiration
      if (notification.expiresAt && new Date(notification.expiresAt) < new Date()) {
        console.log(`Notification ${notification.id} expired, skipping delivery`);
        await this.store.markExpired(notification.id);
        return;
      }

      // Get target user connections on this server
      const userConnections = this.connections.get(notification.userId);
      
      if (userConnections && userConnections.size > 0) {
        let deliveredCount = 0;
        
        for (const ws of userConnections) {
          if (await this.shouldDeliverNotification(ws, notification)) {
            if (ws.readyState === WebSocket.OPEN) {
              // Update sequence tracking if enabled
              if (this.messageOrdering && notification.sequence) {
                (ws as any).lastSeenSequence = notification.sequence;
              }
              
              this.sendMessage(ws, {
                type: 'notification',
                payload: notification,
                sequence: notification.sequence,
                timestamp: Date.now()
              });
              deliveredCount++;
            }
          }
        }
        
        if (deliveredCount > 0) {
          await this.store.markDelivered(
            notification.id,
            this.serverId,
            deliveredCount,
            new Date()
          );
          this.metrics.recordNotificationDelivered(notification.type, deliveredCount);
        } else {
          // User connected but no delivery (e.g., channel mismatch)
          await this.store.markPendingDelivery(notification.id, notification.userId);
        }
      } else {
        // User not connected to this server
        await this.store.markPendingDelivery(notification.id, notification.userId);
        this.metrics.recordNotificationPending(notification.type);
      }
    } catch (error) {
      console.error('Error handling notification:', error);
      this.metrics.recordError('notification_handling', error);
      
      // NEW: Dead letter queue for failed notifications
      await this.store.moveToDeadLetterQueue(notification.id, error.message);
    }
  }

  private async shouldDeliverNotification(
    ws: WebSocket,
    notification: Notification
  ): Promise<boolean> {
    const connectionId = (ws as any).connectionId;
    
    // Check channel subscriptions
    if (notification.channels && notification.channels.length > 0) {
      const subscriptions = await this.redis.getSubscriptions(connectionId);
      
      // NEW: Support wildcard matching
      const matchesSubscription = notification.channels.some(channel => 
        subscriptions.some(sub => this.matchesPattern(channel, sub))
      );
      
      if (!matchesSubscription) {
        return false;
      }
    }
    
    // NEW: Check user preferences (e.g., do not disturb)
    const preferences = await this.store.getUserPreferences((ws as any).userId);
    if (preferences.doNotDisturb && notification.priority !== 'urgent') {
      return false;
    }
    
    return true;
  }

  // NEW: Pattern matching for wildcard subscriptions
  private matchesPattern(channel: string, pattern: string): boolean {
    if (!pattern.includes('*')) {
      return channel === pattern;
    }
    
    const regexPattern = pattern
      .replace(/\./g, '\\.')
      .replace(/\*/g, '.*');
    
    return new RegExp(`^${regexPattern}$`).test(channel);
  }

  private async handleMessage(ws: WebSocket, userId: string, data: string): Promise<void> {
    if (!this.rateLimiter.allowMessage(userId)) {
      this.sendMessage(ws, {
        type: 'error',
        error: 'Rate limit exceeded',
        code: 'RATE_LIMIT_EXCEEDED',
        retryAfter: this.rateLimiter.getRetryAfter(userId)
      });
      return;
    }

    try {
      const message = JSON.parse(data);
      
      if (!message.type) {
        throw new Error('Message type required');
      }
      
      switch (message.type) {
        case 'ping':
          this.sendMessage(ws, { type: 'pong', timestamp: Date.now() });
          break;
        
        case 'subscribe':
          await this.handleSubscribe(ws, userId, message.channels);
          break;
        
        case 'unsubscribe':
          await this.handleUnsubscribe(ws, userId, message.channels);
          break;
        
        case 'ack':
          await this.handleAcknowledgment(ws, userId, message.notificationId);
          break;
        
        // NEW: Batch acknowledgment
        case 'ack_batch':
          await this.handleBatchAcknowledgment(ws, userId, message.notificationIds);
          break;
        
        // NEW: Request missed notifications
        case 'request_missed':
          await this.deliverMissedNotifications(
            ws, 
            userId, 
            message.fromSequence || 0,
            message.limit || 50
          );
          break;
        
        default:
          this.sendMessage(ws, {
            type: 'error',
            error: 'Unknown message type',
            code: 'UNKNOWN_MESSAGE_TYPE'
          });
      }
    } catch (error) {
      console.error('Error parsing/handling message:', error);
      this.sendMessage(ws, {
        type: 'error',
        error: error instanceof Error ? error.message : 'Invalid message format',
        code: 'MESSAGE_PARSE_ERROR'
      });
    }
  }

  private async handleSubscribe(
    ws: WebSocket,
    userId: string,
    channels: string[]
  ): Promise<void> {
    if (!Array.isArray(channels) || channels.length === 0) {
      this.sendMessage(ws, {
        type: 'error',
        error: 'Invalid channels array',
        code: 'INVALID_CHANNELS'
      });
      return;
    }

    const connectionId = (ws as any).connectionId;
    
    // Store subscriptions in Redis (faster access)
    await this.redis.addSubscriptions(connectionId, channels);
    
    // Also persist to DB for recovery
    await this.store.addSubscriptions(connectionId, channels);
    
    this.sendMessage(ws, {
      type: 'subscribed',
      channels,
      timestamp: Date.now()
    });

    this.metrics.recordSubscription(channels.length);
  }

  private async handleUnsubscribe(
    ws: WebSocket,
    userId: string,
    channels: string[]
  ): Promise<void> {
    if (!Array.isArray(channels) || channels.length === 0) {
      this.sendMessage(ws, {
        type: 'error',
        error: 'Invalid channels array',
        code: 'INVALID_CHANNELS'
      });
      return;
    }

    const connectionId = (ws as any).connectionId;
    
    await this.redis.removeSubscriptions(connectionId, channels);
    await this.store.removeSubscriptions(connectionId, channels);
    
    this.sendMessage(ws, {
      type: 'unsubscribed',
      channels,
      timestamp: Date.now()
    });

    this.metrics.recordUnsubscription(channels.length);
  }

  private async handleAcknowledgment(
    ws: WebSocket,
    userId: string,
    notificationId: string
  ): Promise<void> {
    try {
      await this.store.markAcknowledged(notificationId, userId, new Date());
      
      // Remove from pending
      await this.store.removePendingNotification(notificationId, userId);
      
      this.metrics.recordAcknowledgment();
    } catch (error) {
      console.error('Error acknowledging notification:', error);
      this.sendMessage(ws, {
        type: 'error',
        error: 'Failed to acknowledge notification',
        code: 'ACK_FAILED'
      });
    }
  }

  // NEW: Batch acknowledgment for efficiency
  private async handleBatchAcknowledgment(
    ws: WebSocket,
    userId: string,
    notificationIds: string[]
  ): Promise<void> {
    if (!Array.isArray(notificationIds) || notificationIds.length === 0) {
      this.sendMessage(ws, {
        type: 'error',
        error: 'Invalid notification IDs array',
        code: 'INVALID_ACK_BATCH'
      });
      return;
    }

    try {
      await this.store.markAcknowledgedBatch(notificationIds, userId, new Date());
      await this.store.removePendingNotificationsBatch(notificationIds, userId);
      
      this.metrics.recordAcknowledgment(notificationIds.length);
      
      this.sendMessage(ws, {
        type: 'ack_batch_success',
        count: notificationIds.length,
        timestamp: Date.now()
      });
    } catch (error) {
      console.error('Error in batch acknowledgment:', error);
      this.sendMessage(ws, {
        type: 'error',
        error: 'Failed to acknowledge notifications',
        code: 'ACK_BATCH_FAILED'
      });
    }
  }

  // NEW: Enhanced missed notification delivery with ordering
  private async deliverMissedNotifications(
    ws: WebSocket,
    userId: string,
    fromSequence: number = 0,
    limit: number = 50
  ): Promise<void> {
    try {
      const missedNotifications = this.messageOrdering
        ? await this.store.getPendingNotificationsOrdered(userId, fromSequence, limit)
        : await this.store.getPendingNotifications(userId, limit);
      
      let deliveredCount = 0;
      
      for (const notification of missedNotifications) {
        if (ws.readyState === WebSocket.OPEN) {
          this.sendMessage(ws, {
            type: 'notification',
            payload: notification,
            sequence: notification.sequence,
            timestamp: Date.now(),
            missed: true
          });
          
          // Update last seen sequence
          if (this.messageOrdering && notification.sequence) {
            (ws as any).lastSeenSequence = notification.sequence;
          }
          
          deliveredCount++;
        } else {
          break; // Connection closed during delivery
        }
      }

      if (deliveredCount > 0) {
        this.metrics.recordMissedNotificationsDelivered(deliveredCount);
        
        // Send completion marker
        this.sendMessage(ws, {
          type: 'missed_notifications_complete',
          count: deliveredCount,
          hasMore: missedNotifications.length === limit,
          timestamp: Date.now()
        });
      }
    } catch (error) {
      console.error('Error sending missed notifications:', error);
      this.metrics.recordError('missed_notifications', error);
      
      this.sendMessage(ws, {
        type: 'error',
        error: 'Failed to retrieve missed notifications',
        code: 'MISSED_NOTIFICATIONS_FAILED'
      });
    }
  }

  // NEW: Disconnect oldest connection for force reconnect
  private async disconnectOldestConnection(userId: string): Promise<void> {
    const connections = await this.redis.getUserConnections(userId);
    
    if (connections.length === 0) return;
    
    // Sort by connection time (embedded in connection ID)
    connections.sort((a, b) => 
      a.connectionId.localeCompare(b.connectionId)
    );
    
    const oldest = connections[0];
    
    // Send disconnect command to the server holding the connection
    await this.redis.publish('server:commands', {
      command: 'disconnect',
      serverId: oldest.serverId,
      connectionId: oldest.connectionId,
      reason: 'Connection limit exceeded - forced reconnect'
    });
  }

  // NEW: Handle cross-server commands
  private async handleServerCommand(message: string): Promise<void> {
    try {
      const command = JSON.parse(message);
      
      if (command.serverId !== this.serverId) {
        return; // Not for this server
      }
      
      switch (command.command) {
        case 'disconnect':
          await this.forceDisconnectConnection(command.connectionId, command.reason);
          break;
        
        default:
          console.warn(`Unknown server command: ${command.command}`);
      }
    } catch (error) {
      console.error('Error handling server command:', error);
    }
  }

  private async forceDisconnectConnection(
    connectionId: string,
    reason: string
  ): Promise<void> {
    // Find connection in memory
    for (const [userId, connections] of this.connections.entries()) {
      for (const ws of connections) {
        if ((ws as any).connectionId === connectionId) {
          this.sendMessage(ws, {
            type: 'force_disconnect',
            reason,
            timestamp: Date.now()
          });
          
          ws.close(1008, reason);
          return;
        }
      }
    }
  }

  private startHeartbeat(interval: number): void {
    setInterval(() => {
      this.wss.clients.forEach((ws: WebSocket) => {
        if (!(ws as any).isAlive) {
          console.log(`Terminating dead connection: ${(ws as any).connectionId}`);
          return ws.terminate();
        }
        
        (ws as any).isAlive = false;
        ws.ping();
      });
      
      this.metrics.recordHeartbeat(this.wss.clients.size);
    }, interval);
  }

  // NEW: Background jobs for maintenance
  private startBackgroundJobs(): void {
    // Cleanup expired notifications every hour
    setInterval(async () => {
      try {
        const deleted = await this.store.cleanupExpiredNotifications();
        console.log(`Cleaned up ${deleted} expired notifications`);
      } catch (error) {
        console.error('Error in cleanup job:', error);
      }
    }, 3600000); // 1 hour

    // Cleanup old archived connections every 24 hours
    setInterval(async () => {
      try {
        const deleted = await this.store.cleanupArchivedConnections(this.config.offlineRetentionDays);
        console.log(`Cleaned up ${deleted} archived connections`);
      } catch (error) {
        console.error('Error in archive cleanup job:', error);
      }
    }, 86400000); // 24 hours

    // Sync Redis connection state with DB every 5 minutes (recover from Redis failures)
    setInterval(async () => {
      try {
        await this.syncConnectionState();
      } catch (error) {
        console.error('Error syncing connection state:', error);
      }
    }, 300000); // 5 minutes
  }

  private async syncConnectionState(): Promise<void> {
    // Get connections from DB for this server
    const dbConnections = await this.store.getServerConnections(this.serverId);
    
    // Get connections from memory
    const memoryConnections = new Set<string>();
    for (const connections of this.connections.values()) {
      for (const ws of connections) {
        memoryConnections.add((ws as any).connectionId);
      }
    }
    
    // Find orphaned DB records (in DB but not in memory)
    for (const dbConn of dbConnections) {
      if (!memoryConnections.has(dbConn.connectionId)) {
        console.log(`Cleaning up orphaned connection: ${dbConn.connectionId}`);
        await this.store.archiveConnection(dbConn.connectionId);
        await this.redis.removeUserConnection(dbConn.userId, dbConn.connectionId);
      }
    }
  }

  private setupGracefulShutdown(): void {
    const shutdown = async (signal: string) => {
      console.log(`${signal} received, starting graceful shutdown...`);
      this.isShuttingDown = true;

      // Stop accepting new connections
      this.wss.close();

      // Send shutdown notice
      this.wss.clients.forEach((ws: WebSocket) => {
        this.sendMessage(ws, {
          type: 'server_shutdown',
          message: 'Server shutting down, please reconnect',
          timestamp: Date.now()
        });
      });

      // Wait for clients to disconnect
      const shutdownPromise = new Promise<void>((resolve) => {
        const checkInterval = setInterval(() => {
          if (this.wss.clients.size === 0) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);

        setTimeout(() => {
          clearInterval(checkInterval);
          resolve();
        }, this.config.gracefulShutdownTimeout);
      });

      await shutdownPromise;

      // Close remaining connections
      this.wss.clients.forEach(ws => ws.terminate());

      // Cleanup resources
      await this.redis.disconnect();
      await this.store.disconnect();

      console.log('Graceful shutdown complete');
      process.exit(0);
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));
  }

  private sendMessage(ws: WebSocket, message: any): void {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error sending message:', error);
        this.metrics.recordError('send_message', error);
      }
    }
  }

  private generateConnectionId(): string {
    return `${this.serverId}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private extractToken(req: IncomingMessage): string | null {
    const authHeader = req.headers.authorization;
    if (authHeader?.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    
    const url = new URL(req.url!, `http://${req.headers.host}`);
    return url.searchParams.get('token');
  }

  private extractClientIp(req: IncomingMessage): string {
    const forwarded = req.headers['x-forwarded-for'];
    if (typeof forwarded === 'string') {
      return forwarded.split(',')[0].trim();
    }
    return req.socket.remoteAddress || 'unknown';
  }
}
```

### 2. Message Ordering Service

```typescript
// message-ordering.ts
import { RedisClient } from './redis-client';

export class MessageOrderingService {
  private redis: RedisClient;
  private sequenceKey = 'notification:sequence';

  constructor(redis: RedisClient) {
    this.redis = redis;
  }

  async getNextSequence(): Promise<number> {
    return await this.redis.incrementSequence(this.sequenceKey);
  }

  async getLastSeenSequence(userId: string): Promise<number> {
    return await this.redis.getLastSeenSequence(userId);
  }

  async updateLastSeenSequence(userId: string, sequence: number): Promise<void> {
    await this.redis.setLastSeenSequence(userId, sequence);
  }
}
```

### 3. Enhanced Redis Client

```typescript
// redis-client.ts
import { createClient, RedisClientType } from 'redis';

export class RedisClient {
  private client: RedisClientType;
  private publisher: RedisClientType;
  private subscriber: RedisClientType;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;

  constructor(url: string) {
    const config = {
      url,
      socket: {
        reconnectStrategy: (retries: number) => {
          this.reconnectAttempts = retries;
          
          if (retries > this.maxReconnectAttempts) {
            console.error('Max Redis reconnection attempts reached');
            return new Error('Max reconnection attempts reached');
          }
          
          const delay = Math.min(retries * 100, 3000);
          console.log(`Reconnecting to Redis (attempt ${retries}) in ${delay}ms`);
          return delay;
        }
      }
    };

    this.client = createClient(config);
    this.publisher = this.client.duplicate();
    this.subscriber = this.client.duplicate();
    
    this.setupErrorHandlers();
    this.connect();
  }

  private setupErrorHandlers(): void {
    [this.client, this.publisher, this.subscriber].forEach(client => {
      client.on('error', (err) => {
        console.error('Redis client error:', err);
      });

      client.on('connect', () => {
        console.log('Redis client connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
      });

      client.on('disconnect', () => {
        console.log('Redis client disconnected');
        this.isConnected = false;
      });

      client.on('reconnecting', () => {
        console.log('Redis client reconnecting...');
      });
    });
  }

  private async connect(): Promise<void> {
    try {
      await Promise.all([
        this.client.connect(),
        this.publisher.connect(),
        this.subscriber.connect()
      ]);
    } catch (error) {
      console.error('Failed to connect to Redis:', error);
      throw error;
    }
  }

  async publish(channel: string, message: any): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Redis not connected');
    }

    try {
      await this.publisher.publish(channel, JSON.stringify(message));
    } catch (error) {
      console.error('Failed to publish message:', error);
      throw error;
    }
  }

  async subscribe(
    channel: string,
    handler: (message: string) => void
  ): Promise<void> {
    await this.subscriber.subscribe(channel, handler);
  }

  async addUserConnection(userId: string, connectionId: string, serverId: string): Promise<void> {
    const pipeline = this.client.multi();
    pipeline.hSet(`connection:${connectionId}`, {
      userId,
      serverId,
      connectedAt: Date.now()
    });
    pipeline.sAdd(`user:${userId}:connections`, connectionId);
    pipeline.expire(`connection:${connectionId}`, 86400);
    pipeline.expire(`user:${userId}:connections`, 86400);
    await pipeline.exec();
  }

  async removeUserConnection(userId: string, connectionId: string): Promise<void> {
    const pipeline = this.client.multi();
    pipeline.del(`connection:${connectionId}`);
    pipeline.sRem(`user:${userId}:connections`, connectionId);
    await pipeline.exec();
  }

  async getUserConnections(userId: string): Promise<Array<{connectionId: string, serverId: string}>> {
    const connectionIds = await this.client.sMembers(`user:${userId}:connections`);
    const connections = await Promise.all(
      connectionIds.map(async (id) => {
        const data = await this.client.hGetAll(`connection:${id}`);
        return { connectionId: id, serverId: data.serverId };
      })
    );
    return connections.filter(c => c.serverId);
  }

  async getUserConnectionCount(userId: string): Promise<number> {
    return await this.client.sCard(`user:${userId}:connections`);
  }

  // NEW: Subscription management in Redis for fast access
  async addSubscriptions(connectionId: string, channels: string[]): Promise<void> {
    if (channels.length === 0) return;
    
    await this.client.sAdd(`connection:${connectionId}:subscriptions`, channels);
    await this.client.expire(`connection:${connectionId}:subscriptions`, 86400);
  }

  async removeSubscriptions(connectionId: string, channels: string[]): Promise<void> {
    if (channels.length === 0) return;
    
    await this.client.sRem(`connection:${connectionId}:subscriptions`, channels);
  }

  async getSubscriptions(connectionId: string): Promise<string[]> {
    return await this.client.sMembers(`connection:${connectionId}:subscriptions`);
  }

  // NEW: Sequence number management
  async incrementSequence(key: string): Promise<number> {
    return await this.client.incr(key);
  }

  async getLastSeenSequence(userId: string): Promise<number> {
    const seq = await this.client.get(`user:${userId}:last_seq`);
    return seq ? parseInt(seq) : 0;
  }

  async setLastSeenSequence(userId: string, sequence: number): Promise<void> {
    await this.client.set(`user:${userId}:last_seq`, sequence, { EX: 2592000 }); // 30 days
  }

  async disconnect(): Promise<void> {
    await Promise.all([
      this.client.quit(),
      this.publisher.quit(),
      this.subscriber.quit()
    ]);
  }

  isHealthy(): boolean {
    return this.isConnected && this.reconnectAttempts < this.maxReconnectAttempts;
  }
}
```

### 4. Enhanced Notification Store

```typescript
// notification-store.ts
import { Pool, PoolClient } from 'pg';

interface Connection {
  connectionId: string;
  userId: string;
  serverId: string;
  connectedAt: Date;
  lastSeenSequence: number;
  metadata: Record<string, any>;
}

interface Notification {
  id: string;
  userId: string;
  type: string;
  payload: any;
  priority: string;
  channels?: string[];
  sequence?: number;
  expiresAt?: Date;
}

interface UserPreferences {
  doNotDisturb: boolean;
  quietHoursStart?: string;
  quietHoursEnd?: string;
  allowedPriorities?: string[];
}

export class NotificationStore {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({
      connectionString,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    this.pool.on('error', (err) => {
      console.error('Unexpected database error:', err);
    });
  }

  async addConnection(connection: Connection): Promise<void> {
    await this.pool.query(
      `INSERT INTO connections (connection_id, user_id, server_id, connected_at, last_seen_sequence, metadata, archived)
       VALUES ($1, $2, $3, $4, $5, $6, false)
       ON CONFLICT (connection_id) DO UPDATE SET
         connected_at = EXCLUDED.connected_at,
         last_seen_sequence = EXCLUDED.last_seen_sequence,
         metadata = EXCLUDED.metadata,
         archived = false`,
      [
        connection.connectionId,
        connection.userId,
        connection.serverId,
        connection.connectedAt,
        connection.lastSeenSequence,
        JSON.stringify(connection.metadata)
      ]
    );
  }

  async archiveConnection(connectionId: string): Promise<void> {
    await this.pool.query(
      `UPDATE connections SET archived = true, archived_at = NOW()
       WHERE connection_id = $1`,
      [connectionId]
    );
  }

  async getServerConnections(serverId: string): Promise<Array<{connectionId: string, userId: string}>> {
    const result = await this.pool.query(
      `SELECT connection_id, user_id 
       FROM connections 
       WHERE server_id = $1 AND archived = false`,
      [serverId]
    );
    return result.rows.map(row => ({
      connectionId: row.connection_id,
      userId: row.user_id
    }));
  }

  async getConnectionCount(userId: string): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as count 
       FROM connections 
       WHERE user_id = $1 AND archived = false`,
      [userId]
    );
    return parseInt(result.rows[0].count);
  }

  async addSubscriptions(connectionId: string, channels: string[]): Promise<void> {
    if (channels.length === 0) return;

    const values = channels.map((channel, i) => 
      `($1, $${i + 2})`
    ).join(',');
    
    await this.pool.query(
      `INSERT INTO subscriptions (connection_id, channel)
       VALUES ${values}
       ON CONFLICT (connection_id, channel) DO NOTHING`,
      [connectionId, ...channels]
    );
  }

  async removeSubscriptions(connectionId: string, channels: string[]): Promise<void> {
    await this.pool.query(
      `DELETE FROM subscriptions 
       WHERE connection_id = $1 AND channel = ANY($2)`,
      [connectionId, channels]
    );
  }

  async markDelivered(
    notificationId: string, 
    serverId: string, 
    recipientCount: number,
    deliveredAt: Date
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO notification_delivery (notification_id, server_id, delivered_at, recipient_count)
       VALUES ($1, $2, $3, $4)`,
      [notificationId, serverId, deliveredAt, recipientCount]
    );
  }

  async markPendingDelivery(notificationId: string, userId: string): Promise<void> {
    await this.pool.query(
      `INSERT INTO pending_notifications (notification_id, user_id, created_at)
       VALUES ($1, $2, NOW())
       ON CONFLICT (notification_id, user_id) DO NOTHING`,
      [notificationId, userId]
    );
  }

  async markExpired(notificationId: string): Promise<void> {
    await this.pool.query(
      `UPDATE notifications SET status = 'expired' WHERE id = $1`,
      [notificationId]
    );
  }

  async markAcknowledged(notificationId: string, userId: string, acknowledgedAt: Date): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      
      await client.query(
        `UPDATE notification_delivery 
         SET acknowledged_at = $2
         WHERE notification_id = $1`,
        [notificationId, acknowledgedAt]
      );

      await client.query(
        `DELETE FROM pending_notifications
         WHERE notification_id = $1 AND user_id = $2`,
        [notificationId, userId]
      );

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  // NEW: Batch acknowledgment
  async markAcknowledgedBatch(
    notificationIds: string[], 
    userId: string, 
    acknowledgedAt: Date
  ): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      
      await client.query(
        `UPDATE notification_delivery 
         SET acknowledged_at = $2
         WHERE notification_id = ANY($1)`,
        [notificationIds, acknowledgedAt]
      );

      await client.query(
        `DELETE FROM pending_notifications
         WHERE notification_id = ANY($1) AND user_id = $2`,
        [notificationIds, userId]
      );

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async removePendingNotification(notificationId: string, userId: string): Promise<void> {
    await this.pool.query(
      `DELETE FROM pending_notifications
       WHERE notification_id = $1 AND user_id = $2`,
      [notificationId, userId]
    );
  }

  async removePendingNotificationsBatch(notificationIds: string[], userId: string): Promise<void> {
    await this.pool.query(
      `DELETE FROM pending_notifications
       WHERE notification_id = ANY($1) AND user_id = $2`,
      [notificationIds, userId]
    );
  }

  async getPendingNotifications(userId: string, limit: number = 50): Promise<Notification[]> {
    const result = await this.pool.query(
      `SELECT n.id, n.user_id, n.type, n.payload, n.priority, n.channels, n.expires_at, n.sequence
       FROM notifications n
       INNER JOIN pending_notifications pn ON n.id = pn.notification_id
       WHERE pn.user_id = $1 
         AND (n.expires_at IS NULL OR n.expires_at > NOW())
         AND n.status = 'pending'
       ORDER BY n.priority DESC, n.created_at ASC
       LIMIT $2`,
      [userId, limit]
    );

    return result.rows.map(row => ({
      id: row.id,
      userId: row.user_id,
      type: row.type,
      payload: row.payload,
      priority: row.priority,
      channels: row.channels,
      sequence: row.sequence,
      expiresAt: row.expires_at
    }));
  }

  // NEW: Ordered pending notifications
  async getPendingNotificationsOrdered(
    userId: string, 
    fromSequence: number,
    limit: number = 50
  ): Promise<Notification[]> {
    const result = await this.pool.query(
      `SELECT n.id, n.user_id, n.type, n.payload, n.priority, n.channels, n.expires_at, n.sequence
       FROM notifications n
       INNER JOIN pending_notifications pn ON n.id = pn.notification_id
       WHERE pn.user_id = $1 
         AND n.sequence > $2
         AND (n.expires_at IS NULL OR n.expires_at > NOW())
         AND n.status = 'pending'
       ORDER BY n.sequence ASC
       LIMIT $3`,
      [userId, fromSequence, limit]
    );

    return result.rows.map(row => ({
      id: row.id,
      userId: row.user_id,
      type: row.type,
      payload: row.payload,
      priority: row.priority,
      channels: row.channels,
      sequence: row.sequence,
      expiresAt: row.expires_at
    }));
  }

  // NEW: User preferences
  async getUserPreferences(userId: string): Promise<UserPreferences> {
    const result = await this.pool.query(
      `SELECT do_not_disturb, quiet_hours_start, quiet_hours_end, allowed_priorities
       FROM user_preferences
       WHERE user_id = $1`,
      [userId]
    );

    if (result.rows.length === 0) {
      return { doNotDisturb: false };
    }

    const row = result.rows[0];
    return {
      doNotDisturb: row.do_not_disturb,
      quietHoursStart: row.quiet_hours_start,
      quietHoursEnd: row.quiet_hours_end,
      allowedPriorities: row.allowed_priorities
    };
  }

  // NEW: Dead letter queue
  async moveToDeadLetterQueue(notificationId: string, errorMessage: string): Promise<void> {
    await this.pool.query(
      `INSERT INTO dead_letter_queue (notification_id, error_message, failed_at)
       VALUES ($1, $2, NOW())`,
      [notificationId, errorMessage]
    );
  }

  async cleanupExpiredNotifications(): Promise<number> {
    const result = await this.pool.query(
      `DELETE FROM notifications 
       WHERE expires_at IS NOT NULL AND expires_at < NOW()
       RETURNING id`
    );
    return result.rowCount || 0;
  }

  async cleanupArchivedConnections(olderThanDays: number): Promise<number> {
    const result = await this.pool.query(
      `DELETE FROM connections 
       WHERE archived = true 
         AND archived_at < NOW() - INTERVAL '1 day' * $1
       RETURNING connection_id`,
      [olderThanDays]
    );
    return result.rowCount || 0;
  }

  async disconnect(): Promise<void> {
    await this.pool.end();
  }
}
```

### 5. Enhanced Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Connections table with archiving
CREATE TABLE connections (
  connection_id VARCHAR(255) PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  server_id VARCHAR(255) NOT NULL,
  connected_at TIMESTAMP NOT NULL,
  last_seen_sequence BIGINT DEFAULT 0,
  metadata JSONB,
  archived BOOLEAN DEFAULT false,
  archived_at TIMESTAMP,
  INDEX idx_user_id (user_id),
  INDEX idx_server_id (server_id),
  INDEX idx_archived (archived, archived_at) WHERE archived = true
);

-- Subscriptions table
CREATE TABLE subscriptions (
  id SERIAL PRIMARY KEY,
  connection_id VARCHAR(255) NOT NULL,
  channel VARCHAR(255) NOT NULL,
  subscribed_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(connection_id, channel),
  FOREIGN KEY (connection_id) REFERENCES connections(connection_id) ON DELETE CASCADE,
  INDEX idx_connection_channel (connection_id, channel)
);

-- Notifications table with sequence number
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id VARCHAR(255) NOT NULL,
  type VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL,
  priority VARCHAR(20) DEFAULT 'normal',
  channels TEXT[],
  sequence BIGINT,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  INDEX idx_user_created (user_id, created_at),
  INDEX idx_sequence (sequence),
  INDEX idx_expires (expires_at) WHERE expires_at IS NOT NULL,
  INDEX idx_status_priority (status, priority) WHERE status = 'pending'
);

-- Notification delivery tracking
CREATE TABLE notification_delivery (
  id SERIAL PRIMARY KEY,
  notification_id UUID NOT NULL,
  server_id VARCHAR(255) NOT NULL,
  delivered_at TIMESTAMP NOT NULL,
  acknowledged_at TIMESTAMP,
  recipient_count INTEGER DEFAULT 1,
  FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
  INDEX idx_notification (notification_id),
  INDEX idx_acknowledged (acknowledged_at) WHERE acknowledged_at IS NULL
);

-- Pending notifications (offline users)
CREATE TABLE pending_notifications (
  id SERIAL PRIMARY KEY,
  notification_id UUID NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(notification_id, user_id),
  FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
  INDEX idx_user_pending (user_id, created_at)
);

-- NEW: User preferences
CREATE TABLE user_preferences (
  user_id VARCHAR(255) PRIMARY KEY,
  do_not_disturb BOOLEAN DEFAULT false,
  quiet_hours_start TIME,
  quiet_hours_end TIME,
  allowed_priorities TEXT[],
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- NEW: Dead letter queue for failed notifications
CREATE TABLE dead_letter_queue (
  id SERIAL PRIMARY KEY,
  notification_id UUID NOT NULL,
  error_message TEXT,
  failed_at TIMESTAMP NOT NULL,
  retried_count INTEGER DEFAULT 0,
  resolved BOOLEAN DEFAULT false,
  INDEX idx_notification (notification_id),
  INDEX idx_failed (failed_at) WHERE NOT resolved
);

-- Cleanup function for expired notifications
CREATE OR REPLACE FUNCTION cleanup_expired_notifications()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM notifications 
  WHERE expires_at IS NOT NULL AND expires_at < NOW();
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

### 6. Enhanced Client SDK

```typescript
// client-sdk.ts
export interface NotificationClientConfig {
  url: string;
  token: string;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
  heartbeatInterval?: number;
  autoReconnect?: boolean;
  enableOrdering?: boolean;
  forceReconnect?: boolean; // Force disconnect of oldest connection if limit exceeded
}

export class NotificationClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts: number;
  private reconnectDelay: number;
  private heartbeatInterval: number;
  private autoReconnect: boolean;
  private enableOrdering: boolean;
  private forceReconnect: boolean;
  private listeners: Map<string, Set<Function>> = new Map();
  private heartbeatTimer: any = null;
  private connectionId: string | null = null;
  private lastSeenSequence: number = 0;
  private pendingAcknowledgments: Set<string> = new Set();
  private ackBatchTimer: any = null;

  constructor(config: NotificationClientConfig) {
    this.url = config.url;
    this.token = config.token;
    this.maxReconnectAttempts = config.maxReconnectAttempts ?? 5;
    this.reconnectDelay = config.reconnectDelay ?? 1000;
    this.heartbeatInterval = config.heartbeatInterval ?? 30000;
    this.autoReconnect = config.autoReconnect ?? true;
    this.enableOrdering = config.enableOrdering ?? false;
    this.forceReconnect = config.forceReconnect ?? false;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = `${this.url}?token=${encodeURIComponent(this.token)}`;
      this.ws = new WebSocket(wsUrl);

      // Add force reconnect header if enabled
      if (this.forceReconnect && this.reconnectAttempts > 0) {
        // Note: WebSocket API doesn't support custom headers directly
        // This would need to be implemented via query parameter or initial handshake
      }

      const connectTimeout = setTimeout(() => {
        if (this.ws?.readyState !== WebSocket.OPEN) {
          this.ws?.close();
          reject(new Error('Connection timeout'));
        }
      }, 10000);

      this.ws.onopen = () => {
        clearTimeout(connectTimeout);
        console.log('Connected to notification service');
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          this.handleMessage(event.data);
        } catch (error) {
          console.error('Error handling message:', error);
        }
      };

      this.ws.onerror = (error) => {
        clearTimeout(connectTimeout);
        console.error('WebSocket error:', error);
        this.emit('error', error);
      };

      this.ws.onclose = (event) => {
        clearTimeout(connectTimeout);
        this.stopHeartbeat();
        this.flushAcknowledgments(); // Send pending acks before disconnect
        
        console.log(`Disconnected from notification service (code: ${event.code})`);
        this.emit('disconnected', { code: event.code, reason: event.reason });
        
        if (this.autoReconnect && event.code !== 1000) {
          this.handleReconnect();
        }
      };
    });
  }

  private handleMessage(data: string): void {
    const message = JSON.parse(data);
    
    switch (message.type) {
      case 'connected':
        this.connectionId = message.connectionId;
        this.lastSeenSequence = message.lastSeenSequence || 0;
        this.emit('connected', message);
        break;

      case 'notification':
        // Update sequence if ordering enabled
        if (this.enableOrdering && message.sequence) {
          this.lastSeenSequence = Math.max(this.lastSeenSequence, message.sequence);
        }
        
        this.emit('notification', message.payload);
        
        // Auto-acknowledge with batching
        if (message.payload.id) {
          this.queueAcknowledgment(message.payload.id);
        }
        break;

      case 'missed_notifications_complete':
        this.emit('missed_notifications_complete', message);
        break;

      case 'pong':
        this.emit('pong', message);
        break;

      case 'server_shutdown':
        this.emit('server_shutdown', message);
        break;

      case 'force_disconnect':
        this.emit('force_disconnect', message);
        break;

      case 'error':
        this.emit('error', message);
        break;

      default:
        this.emit(message.type, message);
    }
    
    this.emit('message', message);
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('max_reconnect', {});
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });
    
    setTimeout(() => {
      this.connect().catch(err => {
        console.error('Reconnection failed:', err);
      });
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.ping();
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  ping(): void {
    this.send({ type: 'ping', timestamp: Date.now() });
  }

  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: Function): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  private emit(event: string, data: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in ${event} handler:`, error);
        }
      });
    }
  }

  subscribe(channels: string[]): void {
    if (!Array.isArray(channels) || channels.length === 0) {
      throw new Error('channels must be a non-empty array');
    }
    this.send({ type: 'subscribe', channels });
  }

  unsubscribe(channels: string[]): void {
    if (!Array.isArray(channels) || channels.length === 0) {
      throw new Error('channels must be a non-empty array');
    }
    this.send({ type: 'unsubscribe', channels });
  }

  acknowledge(notificationId: string): void {
    this.send({ type: 'ack', notificationId });
  }

  // NEW: Batched acknowledgment for efficiency
  private queueAcknowledgment(notificationId: string): void {
    this.pendingAcknowledgments.add(notificationId);
    
    // Clear existing timer
    if (this.ackBatchTimer) {
      clearTimeout(this.ackBatchTimer);
    }
    
    // Batch acks together (send after 1 second or 10 acks, whichever comes first)
    if (this.pendingAcknowledgments.size >= 10) {
      this.flushAcknowledgments();
    } else {
      this.ackBatchTimer = setTimeout(() => {
        this.flushAcknowledgments();
      }, 1000);
    }
  }

  private flushAcknowledgments(): void {
    if (this.pendingAcknowledgments.size === 0) return;
    
    const ids = Array.from(this.pendingAcknowledgments);
    this.pendingAcknowledgments.clear();
    
    if (this.ackBatchTimer) {
      clearTimeout(this.ackBatchTimer);
      this.ackBatchTimer = null;
    }
    
    if (ids.length === 1) {
      this.send({ type: 'ack', notificationId: ids[0] });
    } else {
      this.send({ type: 'ack_batch', notificationIds: ids });
    }
  }

  // NEW: Request missed notifications explicitly
  requestMissedNotifications(fromSequence?: number, limit?: number): void {
    this.send({ 
      type: 'request_missed',
      fromSequence: fromSequence ?? this.lastSeenSequence,
      limit: limit ?? 50
    });
  }

  private send(message: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('WebSocket is not connected');
      throw new Error('Not connected');
    }
    this.ws.send(JSON.stringify(message));
  }

  disconnect(): void {
    this.autoReconnect = false;
    this.stopHeartbeat();
    this.flushAcknowledgments(); // Send any pending acks
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getConnectionId(): string | null {
    return this.connectionId;
  }

  getLastSeenSequence(): number {
    return this.lastSeenSequence;
  }
}
```