# Final Agreed Design

**Task:** Design a visual AI agent workflow builder

Requirements:
- Drag-and-drop nodes for different agent types (researcher, coder, reviewer)
- Connect nodes to show data flow between agents
- Configure each node (model, temperature, system prompt)
- Show real-time execution status and logs
- Visualize agent communication/handoffs
- Save and load workflow templates
- React with a canvas library

**Status:** debating

---

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v5

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Resilient │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Stream    │  │  Manager   │         │  │
│  │  │            │  │  Manager   │  │            │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Composable │  │   Tiered   │  │ Effect Log │         │  │
│  │  │ Expression │  │  Storage   │  │  (Append-  │         │  │
│  │  │  System    │  │  Manager   │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with viewport culling
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Adaptive executor with resilient streaming
- **Storage**: Three-tier (Memory + IndexedDB + SessionStorage) with per-workflow policies
- **Expressions**: Composable expression system with visual-text hybrid mode
- **Side Effects**: Append-only log with sandboxed compensation handlers
- **Workers**: Shared Worker pool with resource quotas

## Resilient Stream Manager (Solves Page Refresh Problem)

### Key Innovation: Automatic Checkpoint-Based Stream Resurrection

```typescript
interface StreamManagerConfig {
  maxConcurrentStreams: number;        // 50
  streamTimeout: number;                // 5min
  autoCheckpointInterval: number;       // 30s - checkpoint long-lived streams
  checkpointThresholdAge: number;       // 60s - checkpoint if older than this
  enableResurrection: boolean;          // Restore streams after page refresh
  maxResurrectionAttempts: number;      // 3
}

interface StreamCheckpoint {
  streamId: string;
  sourceNodeId: string;
  executionId: string;
  consumerCount: number;
  createdAt: number;
  lastCheckpointAt: number;
  
  // Resurrection data
  materializationType: 'full' | 'partial' | 'regenerate';
  materializedData?: any;               // For 'full' or 'partial'
  partialOffset?: number;               // Where partial stopped
  regenerationConfig?: {                // For 'regenerate'
    nodeConfig: any;
    inputs: Record<string, any>;
  };
  
  // State
  status: 'active' | 'checkpointed' | 'resurrected' | 'expired';
  resurrectionAttempts: number;
}

class ResilientStreamManager {
  private activeStreams: Map<string, ActiveStreamEntry> = new Map();
  private checkpoints: Map<string, StreamCheckpoint> = new Map();
  private storage: HybridStorageManager;
  private config: StreamManagerConfig;
  
  constructor(storage: HybridStorageManager, config: StreamManagerConfig) {
    this.storage = storage;
    this.config = config;
    
    // Restore checkpoints from previous session
    if (config.enableResurrection) {
      this.restoreCheckpointsFromStorage();
    }
    
    this.startAutoCheckpointing();
    this.startTimeoutMonitor();
  }
  
  async registerStream(
    sourceNodeId: string,
    executionId: string,
    stream: ReadableStream,
    consumerCount: number,
    options: {
      estimatedSize: number;
      materializationType?: 'full' | 'partial' | 'regenerate';
      regenerationConfig?: any;
    }
  ): Promise<string> {
    
    if (this.activeStreams.size >= this.config.maxConcurrentStreams) {
      throw new Error(
        `Max concurrent streams reached (${this.config.maxConcurrentStreams})`
      );
    }
    
    const streamId = crypto.randomUUID();
    
    // Create teed streams
    const teedStreams = this.createMultiTee(stream, consumerCount);
    
    // Create checkpoint
    const checkpoint: StreamCheckpoint = {
      streamId,
      sourceNodeId,
      executionId,
      consumerCount,
      createdAt: Date.now(),
      lastCheckpointAt: Date.now(),
      materializationType: options.materializationType ?? 'full',
      regenerationConfig: options.regenerationConfig,
      status: 'active',
      resurrectionAttempts: 0
    };
    
    this.checkpoints.set(streamId, checkpoint);
    
    this.activeStreams.set(streamId, {
      checkpoint,
      streams: teedStreams,
      readers: new Set(),
      materializedChunks: options.materializationType !== 'regenerate' ? [] : undefined
    });
    
    return streamId;
  }
  
  async getStream(streamId: string, consumerIndex: number): Promise<ReadableStream> {
    const active = this.activeStreams.get(streamId);
    
    if (active) {
      // Stream is live
      active.checkpoint.lastCheckpointAt = Date.now();
      return active.streams[consumerIndex];
    }
    
    // Try to resurrect from checkpoint
    if (this.config.enableResurrection) {
      const resurrected = await this.resurrectStream(streamId, consumerIndex);
      if (resurrected) return resurrected;
    }
    
    throw new Error(`Stream not found and could not be resurrected: ${streamId}`);
  }
  
  private async resurrectStream(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStream | null> {
    
    const checkpoint = this.checkpoints.get(streamId);
    if (!checkpoint) return null;
    
    if (checkpoint.resurrectionAttempts >= this.config.maxResurrectionAttempts) {
      console.error(`Max resurrection attempts reached for stream ${streamId}`);
      return null;
    }
    
    checkpoint.resurrectionAttempts++;
    
    try {
      switch (checkpoint.materializationType) {
        case 'full':
          return await this.resurrectFromFullMaterialization(checkpoint);
          
        case 'partial':
          return await this.resurrectFromPartialMaterialization(checkpoint);
          
        case 'regenerate':
          return await this.resurrectViaRegeneration(checkpoint);
          
        default:
          throw new Error(`Unknown materialization type: ${checkpoint.materializationType}`);
      }
    } catch (error: any) {
      console.error(`Stream resurrection failed: ${error.message}`);
      return null;
    }
  }
  
  private async resurrectFromFullMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    // Load materialized data from storage
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const materialized = await this.storage.retrieve(storageKey);
    
    // Convert back to stream
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(materialized)) {
          for (const chunk of materialized) {
            controller.enqueue(chunk);
          }
        } else {
          controller.enqueue(materialized);
        }
        controller.close();
      }
    });
    
    checkpoint.status = 'resurrected';
    
    return stream;
  }
  
  private async resurrectFromPartialMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    // Load partial data
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const partialData = await this.storage.retrieve(storageKey);
    
    // Return stream that first emits partial data, then signals "incomplete"
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(partialData)) {
          for (const chunk of partialData) {
            controller.enqueue(chunk);
          }
        }
        
        // Signal incomplete
        controller.enqueue({
          $incomplete: true,
          offset: checkpoint.partialOffset,
          message: 'Stream was interrupted. Partial data only.'
        });
        
        controller.close();
      }
    });
    
    checkpoint.status = 'resurrected';
    
    return stream;
  }
  
  private async resurrectViaRegeneration(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    if (!checkpoint.regenerationConfig) {
      throw new Error('No regeneration config available');
    }
    
    // Re-execute the node to regenerate the stream
    // This requires access to the executor (injected via callback)
    const regenerated = await this.executeNodeForRegeneration(
      checkpoint.sourceNodeId,
      checkpoint.regenerationConfig.nodeConfig,
      checkpoint.regenerationConfig.inputs
    );
    
    checkpoint.status = 'resurrected';
    
    return regenerated;
  }
  
  private async executeNodeForRegeneration(
    nodeId: string,
    nodeConfig: any,
    inputs: Record<string, any>
  ): Promise<ReadableStream> {
    
    // This is called by injecting an executor callback during initialization
    // For now, throw error to indicate implementation needed
    throw new Error(
      'Regeneration requires executor callback. ' +
      'Set ResilientStreamManager.regenerationExecutor = (node, inputs) => stream'
    );
  }
  
  private startAutoCheckpointing(): void {
    setInterval(() => {
      this.checkpointLongLivedStreams();
    }, this.config.autoCheckpointInterval);
  }
  
  private async checkpointLongLivedStreams(): Promise<void> {
    const now = Date.now();
    const threshold = this.config.checkpointThresholdAge;
    
    for (const [streamId, entry] of this.activeStreams.entries()) {
      const age = now - entry.checkpoint.createdAt;
      
      if (age > threshold && entry.checkpoint.status === 'active') {
        await this.checkpointStream(streamId);
      }
    }
  }
  
  private async checkpointStream(streamId: string): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    const checkpoint = entry.checkpoint;
    
    switch (checkpoint.materializationType) {
      case 'full':
        // Materialize all consumed chunks so far
        if (entry.materializedChunks && entry.materializedChunks.length > 0) {
          const storageKey = `stream-checkpoint-${streamId}`;
          checkpoint.materializedData = [...entry.materializedChunks];
          
          await this.storage.store(storageKey, checkpoint.materializedData, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'partial':
        // Only keep last N chunks
        if (entry.materializedChunks) {
          const keepCount = 10;
          const partial = entry.materializedChunks.slice(-keepCount);
          
          const storageKey = `stream-checkpoint-${streamId}`;
          await this.storage.store(storageKey, partial, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.partialOffset = entry.materializedChunks.length - keepCount;
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'regenerate':
        // No materialization needed - regeneration config already stored
        checkpoint.status = 'checkpointed';
        checkpoint.lastCheckpointAt = Date.now();
        break;
    }
    
    // Persist checkpoint metadata to SessionStorage
    await this.persistCheckpoint(checkpoint);
  }
  
  private async persistCheckpoint(checkpoint: StreamCheckpoint): Promise<void> {
    const key = `stream-checkpoint-meta-${checkpoint.streamId}`;
    sessionStorage.setItem(key, JSON.stringify(checkpoint));
  }
  
  private async restoreCheckpointsFromStorage(): Promise<void> {
    const keys = Object.keys(sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('stream-checkpoint-meta-')) {
        const checkpointData = sessionStorage.getItem(key);
        if (checkpointData) {
          const checkpoint: StreamCheckpoint = JSON.parse(checkpointData);
          this.checkpoints.set(checkpoint.streamId, checkpoint);
        }
      }
    }
  }
  
  private createMultiTee(stream: ReadableStream, count: number): ReadableStream[] {
    if (count === 1) return [stream];
    if (count === 2) return stream.tee();
    
    const streams: ReadableStream[] = [];
    let remaining = stream;
    
    for (let i = 0; i < count - 1; i++) {
      const [stream1, stream2] = remaining.tee();
      streams.push(stream1);
      remaining = stream2;
    }
    streams.push(remaining);
    
    return streams;
  }
  
  async acquireReader(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStreamDefaultReader> {
    const stream = await this.getStream(streamId, consumerIndex);
    const reader = stream.getReader();
    
    const entry = this.activeStreams.get(streamId);
    if (entry) {
      entry.readers.add(reader);
      
      // Wrap reader to capture chunks for checkpointing
      if (entry.materializedChunks) {
        return this.wrapReaderForCheckpointing(reader, entry.materializedChunks);
      }
    }
    
    return reader;
  }
  
  private wrapReaderForCheckpointing(
    reader: ReadableStreamDefaultReader,
    chunksBuffer: any[]
  ): ReadableStreamDefaultReader {
    
    const originalRead = reader.read.bind(reader);
    
    reader.read = async () => {
      const result = await originalRead();
      
      if (!result.done && result.value !== undefined) {
        chunksBuffer.push(result.value);
      }
      
      return result;
    };
    
    return reader;
  }
  
  async releaseReader(
    streamId: string, 
    reader: ReadableStreamDefaultReader
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    try {
      reader.releaseLock();
    } catch {
      // Already released
    }
    
    entry.readers.delete(reader);
    
    if (entry.readers.size === 0) {
      await this.cleanup(streamId, 'completed');
    }
  }
  
  private async cleanup(
    streamId: string, 
    reason: 'completed' | 'error' | 'timeout'
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    // Final checkpoint before cleanup
    if (reason === 'completed' && entry.checkpoint.materializationType !== 'regenerate') {
      await this.checkpointStream(streamId);
    }
    
    entry.checkpoint.status = 'expired';
    
    for (const stream of entry.streams) {
      try {
        const reader = stream.getReader();
        await reader.cancel(`Cleanup: ${reason}`);
        reader.releaseLock();
      } catch {
        // Ignore
      }
    }
    
    this.activeStreams.delete(streamId);
  }
  
  private startTimeoutMonitor(): void {
    setInterval(() => {
      const now = Date.now();
      const timeout = this.config.streamTimeout;
      
      for (const [streamId, entry] of this.activeStreams.entries()) {
        if (now - entry.checkpoint.lastCheckpointAt > timeout) {
          console.warn(`Stream timeout: ${streamId}`);
          this.cleanup(streamId, 'timeout');
        }
      }
    }, 60000);
  }
  
  getCheckpoint(streamId: string): StreamCheckpoint | null {
    return this.checkpoints.get(streamId) ?? null;
  }
  
  listActiveStreams(): StreamCheckpoint[] {
    return Array.from(this.activeStreams.values())
      .map(entry => entry.checkpoint);
  }
  
  // Public property for injecting regeneration logic
  regenerationExecutor?: (
    nodeId: string, 
    nodeConfig: any, 
    inputs: Record<string, any>
  ) => Promise<ReadableStream>;
}

interface ActiveStreamEntry {
  checkpoint: StreamCheckpoint;
  streams: ReadableStream[];
  readers: Set<ReadableStreamDefaultReader>;
  materializedChunks?: any[];  // For 'full' or 'partial' checkpointing
}
```

## Enhanced Tiered Storage with Per-Workflow Policies

### Key Innovation: Workflow-Scoped Storage Configuration

```typescript
interface WorkflowStoragePolicy {
  workflowId: string;
  
  // Tier capacities (per workflow)
  memoryCacheMaxBytes: number;          // Default: 50MB per workflow
  indexedDBMaxBytes: number;            // Default: 500MB per workflow
  
  // Overflow behavior
  overflowPolicy: 'evict-lru' | 'evict-oldest' | 'fail' | 'compress' | 'external';
  
  // Eviction preferences
  evictionPreferences: {
    protectRecent: boolean;             // Don't evict < 5s old
    protectFrequent: boolean;           // Prefer low-access items
    protectPinned: boolean;             // Never evict pinned
  };
  
  // Auto-cleanup
  autoCleanupAge: number;               // 24h
  enableAutoCleanup: boolean;
}

class TieredStorageManager {
  private memoryCache: Map<string, CacheEntry> = new Map();
  private memoryCacheSize: number = 0;
  private indexedDB: IDBDatabase;
  private indexedDBSize: number = 0;
  
  // Per-workflow policies
  private workflowPolicies: Map<string, WorkflowStoragePolicy> = new Map();
  private globalPolicy: WorkflowStoragePolicy;
  
  // Artifact metadata
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  
  // External blobs
  private externalBlobs: Map<string, string> = new Map();
  
  // Session-level temporary storage (survives refresh)
  private sessionStorage: Storage = window.sessionStorage;
  
  constructor(globalPolicy: WorkflowStoragePolicy) {
    this.globalPolicy = globalPolicy;
    this.initIndexedDB();
    this.restoreFromSession();
  }
  
  setWorkflowPolicy(workflowId: string, policy: WorkflowStoragePolicy): void {
    this.workflowPolicies.set(workflowId, policy);
  }
  
  getPolicy(workflowId?: string): WorkflowStoragePolicy {
    if (workflowId) {
      return this.workflowPolicies.get(workflowId) ?? this.globalPolicy;
    }
    return this.globalPolicy;
  }
  
  async store(
    key: string, 
    data: any, 
    hints: StorageHints = {}
  ): Promise<void> {
    
    const policy = this.getPolicy(hints.workflowId);
    const serialized = JSON.stringify(data);
    const sizeBytes = new TextEncoder().encode(serialized).length;
    
    // Create metadata
    const metadata: ArtifactMetadata = {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      lastAccessedAt: Date.now(),
      accessCount: 0,
      temporary: hints.temporary ?? true,
      pinned: hints.pinned ?? false,
      nodeId: hints.nodeId,
      executionId: hints.executionId,
      workflowId: hints.workflowId,
      dataType: hints.dataType ?? 'json'
    };
    
    this.artifactIndex.set(key, metadata);
    
    // Check if we should use session storage (for critical workflow state)
    if (hints.useSessionStorage) {
      this.sessionStorage.setItem(key, serialized);
      metadata.tier = 'session';
      return;
    }
    
    // Tier decision
    if (sizeBytes < 1024 * 1024) {
      if (await this.tryStoreInMemory(key, data, sizeBytes, policy)) {
        metadata.tier = 'memory';
        return;
      }
    }
    
    await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
    metadata.tier = 'indexeddb';
  }
  
  private async tryStoreInMemory(
    key: string, 
    data: any, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    if (this.memoryCacheSize + sizeBytes <= policy.memoryCacheMaxBytes) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    if (await this.evictFromMemory(sizeBytes, policy)) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    return false;
  }
  
  private async evictFromMemory(
    requiredBytes: number, 
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'memory' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        (!policy.evictionPreferences.protectRecent || 
         Date.now() - m.createdAt > 5000)
      );
    
    // Sort by policy
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const metadata of candidates) {
      toEvict.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (freedBytes < requiredBytes) return false;
    
    for (const key of toEvict) {
      const entry = this.memoryCache.get(key)!;
      await this.storeInIndexedDB(key, JSON.stringify(entry.data), entry.sizeBytes, policy);
      
      this.memoryCache.delete(key);
      this.memoryCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        metadata.tier = 'indexeddb';
      }
    }
    
    return true;
  }
  
  private async storeInIndexedDB(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    if (this.indexedDBSize + sizeBytes > policy.indexedDBMaxBytes) {
      await this.handleIndexedDBOverflow(key, serialized, sizeBytes, policy);
      return;
    }
    
    const shouldCompress = sizeBytes > 1024 * 1024;
    const toStore = shouldCompress 
      ? await this.compress(serialized)
      : serialized;
    
    const actualSize = shouldCompress 
      ? new TextEncoder().encode(toStore).length 
      : sizeBytes;
    
    const tx = this.indexedDB.transaction('artifacts', 'readwrite');
    await tx.objectStore('artifacts').put({
      key,
      data: toStore,
      compressed: shouldCompress,
      sizeBytes: actualSize,
      storedAt: Date.now()
    });
    
    this.indexedDBSize += actualSize;
  }
  
  private async handleIndexedDBOverflow(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    switch (policy.overflowPolicy) {
      case 'evict-lru':
      case 'evict-oldest':
        await this.evictFromIndexedDB(sizeBytes, policy);
        await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
        break;
        
      case 'fail':
        throw new StorageFullError(
          `Storage full for workflow: ${policy.workflowId}`,
          this.getStorageStats()
        );
        
      case 'compress':
        const compressed = await this.compress(serialized);
        const compressedSize = new TextEncoder().encode(compressed).length;
        
        if (this.indexedDBSize + compressedSize > policy.indexedDBMaxBytes) {
          await this.evictFromIndexedDB(compressedSize, policy);
        }
        
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').put({
          key,
          data: compressed,
          compressed: true,
          sizeBytes: compressedSize,
          storedAt: Date.now()
        });
        
        this.indexedDBSize += compressedSize;
        break;
        
      case 'external':
        const blob = new Blob([await this.compress(serialized)]);
        const blobUrl = URL.createObjectURL(blob);
        
        this.externalBlobs.set(key, blobUrl);
        
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').put({
          key,
          blobUrl,
          sizeBytes,
          storedAt: Date.now()
        });
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) {
          metadata.tier = 'external';
        }
        break;
    }
  }
  
  private async evictFromIndexedDB(
    requiredBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'indexeddb' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        m.workflowId === policy.workflowId  // Only evict from same workflow
      );
    
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toDelete: string[] = [];
    
    for (const metadata of candidates) {
      toDelete.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (toDelete.length === 0) {
      throw new Error('Cannot evict: all items protected or wrong workflow');
    }
    
    const txDelete = this.indexedDB.transaction('artifacts', 'readwrite');
    const storeDelete = txDelete.objectStore('artifacts');
    
    for (const key of toDelete) {
      await storeDelete.delete(key);
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        this.indexedDBSize -= metadata.sizeBytes;
      }
      this.artifactIndex.delete(key);
    }
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    switch (metadata.tier) {
      case 'memory':
        return this.memoryCache.get(key)?.data;
        
      case 'indexeddb':
        return await this.retrieveFromIndexedDB(key);
        
      case 'session':
        const sessionData = this.sessionStorage.getItem(key);
        return sessionData ? JSON.parse(sessionData) : null;
        
      case 'external':
        return await this.retrieveFromExternalBlob(key);
        
      default:
        throw new Error(`Unknown tier: ${metadata.tier}`);
    }
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const record = await tx.objectStore('artifacts').get(key);
    
    if (!record) {
      throw new Error(`Artifact not in IndexedDB: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async retrieveFromExternalBlob(key: string): Promise<any> {
    const blobUrl = this.externalBlobs.get(key);
    if (!blobUrl) {
      throw new Error(`External blob not found: ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = await response.text();
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  async pin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = true;
    }
  }
  
  async unpin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = false;
    }
  }
  
  private async compress(data: string): Promise<string> {
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    const uint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...uint8));
  }
  
  private async decompress(data: string): Promise<string> {
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowStorage', 4);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.indexedDB = request.result;
        this.calculateIndexedDBSize();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          const store = db.createObjectStore('artifacts', { keyPath: 'key' });
          store.createIndex('storedAt', 'storedAt', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('blobRefs')) {
          db.createObjectStore('blobRefs', { keyPath: 'key' });
        }
      };
    });
  }
  
  private async calculateIndexedDBSize(): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    let cursor = await store.openCursor();
    
    let totalSize = 0;
    while (cursor) {
      totalSize += cursor.value.sizeBytes || 0;
      cursor = await cursor.continue();
    }
    
    this.indexedDBSize = totalSize;
  }
  
  private restoreFromSession(): void {
    // Restore critical workflow state from session storage
    const keys = Object.keys(this.sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('workflow-')) {
        const metadata: ArtifactMetadata = {
          key,
          sizeBytes: this.sessionStorage.getItem(key)!.length,
          tier: 'session',
          createdAt: Date.now(),
          lastAccessedAt: Date.now(),
          accessCount: 0,
          temporary: false,
          pinned: true,
          dataType: 'json'
        };
        
        this.artifactIndex.set(key, metadata);
      }
    }
  }
  
  getStorageStats(workflowId?: string): StorageStats {
    const stats = {
      memory: { count: 0, bytes: this.memoryCacheSize },
      indexeddb: { count: 0, bytes: this.indexedDBSize },
      session: { count: 0, bytes: 0 },
      external: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      if (workflowId && metadata.workflowId !== workflowId) continue;
      
      stats[metadata.tier as keyof typeof stats].count++;
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
}

interface CacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface StorageHints {
  temporary?: boolean;
  pinned?: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType?: 'stream-ref' | 'materialized' | 'blob' | 'json';
  useSessionStorage?: boolean;
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: 'memory' | 'indexeddb' | 'session' | 'external' | 'determining';
  createdAt: number;
  lastAccessedAt: number;
  accessCount: number;
  temporary: boolean;
  pinned: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType: 'stream-ref' | 'materialized' | 'blob' | 'json';
}

interface StorageStats {
  memory: { count: number; bytes: number };
  indexeddb: { count: number; bytes: number };
  session: { count: number; bytes: number };
  external: { count: number; bytes: number };
  total: { count: number; bytes: number };
}

class StorageFullError extends Error {
  constructor(message: string, public stats: StorageStats) {
    super(message);
    this.name = 'StorageFullError';
  }
}
```

## Visual-Text Hybrid Expression Editor

### Key Innovation: Rich Text Editor with Inline Block Components

```typescript
interface HybridExpression {
  mode: 'hybrid';
  content: EditorContent[];  // Prosemirror-style content
  rawText: string;           // Plain text with markers (for serialization)
}

type EditorContent = TextNode | BlockNode;

interface TextNode {
  type: 'text';
  text: string;
}

interface BlockNode {
  type: 'block';
  blockType: 'field' | 'filter' | 'map' | 'aggregate' | 'transform';
  config: Record<string, any>;
  displayText: string;  // Human-readable representation
}

class HybridExpressionEditor {
  private engine: ComposableExpressionEngine;
  
  constructor() {
    this.engine = new ComposableExpressionEngine();
  }
  
  parseFromText(text: string): HybridExpression {
    const content: EditorContent[] = [];
    const blockMarkerRegex = /\{\{block:([^:}]+):([^}]+)\}\}/g;
    
    let lastIndex = 0;
    const matches = text.matchAll(blockMarkerRegex);
    
    for (const match of matches) {
      // Add text before block
      if (match.index! > lastIndex) {
        const textPart = text.slice(lastIndex, match.index);
        if (textPart) {
          content.push({ type: 'text', text: textPart });
        }
      }
      
      // Parse block
      const [_, blockType, configStr] = match;
      const config = this.parseBlockConfig(blockType, configStr);
      const displayText = this.generateDisplayText(blockType, config);
      
      content.push({
        type: 'block',
        blockType: blockType as any,
        config,
        displayText
      });
      
      lastIndex = match.index! + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      content.push({ type: 'text', text: text.slice(lastIndex) });
    }
    
    return {
      mode: 'hybrid',
      content,
      rawText: text
    };
  }
  
  serializeToText(expression: HybridExpression): string {
    return expression.content.map(node => {
      if (node.type === 'text') {
        return node.text;
      } else {
        const configStr = this.serializeBlockConfig(node.blockType, node.config);
        return `{{block:${node.blockType}:${configStr}}}`;
      }
    }).join('');
  }
  
  private parseBlockConfig(type: string, configStr: string): Record<string, any> {
    const pairs = configStr.split(':');
    
    switch (type) {
      case 'field':
        return { path: pairs[0] };
      case 'filter':
        return { condition: pairs[0] };
      case 'aggregate':
        return { function: pairs[0], path: pairs[1] || '' };
      case 'map':
        return { expression: pairs[0] };
      case 'transform':
        return { operation: pairs[0] };
      default:
        return {};
    }
  }
  
  private serializeBlockConfig(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return config.path;
      case 'filter':
        return config.condition;
      case 'aggregate':
        return `${config.function}:${config.path}`;
      case 'map':
        return config.expression;
      case 'transform':
        return config.operation;
      default:
        return '';
    }
  }
  
  private generateDisplayText(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return `$.${config.path}`;
      case 'filter':
        return `[${config.condition}]`;
      case 'aggregate':
        return `${config.function}(${config.path})`;
      case 'map':
        return `map(${config.expression})`;
      case 'transform':
        return config.operation;
      default:
        return 'block';
    }
  }
  
  insertBlock(
    expression: HybridExpression, 
    cursorPosition: number,
    blockType: string,
    config: Record<string, any>
  ): HybridExpression {
    
    const displayText = this.generateDisplayText(blockType, config);
    const blockNode: BlockNode = {
      type: 'block',
      blockType: blockType as any,
      config,
      displayText
    };
    
    // Find position in content array
    let currentPos = 0;
    let insertIndex = 0;
    
    for (let i = 0; i < expression.content.length; i++) {
      const node = expression.content[i];
      const nodeLength = node.type === 'text' 
        ? node.text.length 
        : node.displayText.length;
      
      if (currentPos + nodeLength >= cursorPosition) {
        insertIndex = i + 1;
        break;
      }
      
      currentPos += nodeLength;
    }
    
    const newContent = [
      ...expression.content.slice(0, insertIndex),
      blockNode,
      ...expression.content.slice(insertIndex)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
  
  removeBlock(expression: HybridExpression, blockIndex: number): HybridExpression {
    const newContent = expression.content.filter((_, i) => i !== blockIndex);
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
  
  updateBlock(
    expression: HybridExpression, 
    blockIndex: number,
    newConfig: Record<string, any>
  ): HybridExpression {
    
    const node = expression.content[blockIndex];
    if (node.type !== 'block') {
      throw new Error('Node is not a block');
    }
    
    const updatedNode: BlockNode = {
      ...node,
      config: newConfig,
      displayText: this.generateDisplayText(node.blockType, newConfig)
    };
    
    const newContent = [
      ...expression.content.slice(0, blockIndex),
      updatedNode,
      ...expression.content.slice(blockIndex + 1)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
}

// React Component
const HybridExpressionEditorUI: React.FC<{
  value: HybridExpression;
  onChange: (value: HybridExpression) => void;
}> = ({ value, onChange }) => {
  
  const editor = useMemo(() => new HybridExpressionEditor(), []);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [selectedBlockIndex, setSelectedBlockIndex] = useState<number | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  
  const handleInsertBlock = (blockType: string) => {
    const defaultConfig = getDefaultBlockConfig(blockType);
    const updated = editor.insertBlock(value, cursorPosition, blockType, defaultConfig);
    onChange(updated);
  };
  
  const handleRemoveBlock = (blockIndex: number) => {
    const updated = editor.removeBlock(value, blockIndex);
    onChange(updated);
    setSelectedBlockIndex(null);
  };
  
  const handleUpdateBlock = (blockIndex: number, newConfig: Record<string, any>) => {
    const updated = editor.updateBlock(value, blockIndex, newConfig);
    onChange(updated);
  };
  
  const handleTextChange = (newText: string) => {
    const parsed = editor.parseFromText(newText);
    onChange(parsed);
  };
  
  return (
    <div className="hybrid-expression-editor">
      {/* Block Palette */}
      <div className="block-palette">
        <button onClick={() => handleInsertBlock('field')}>
          <span className="icon">📄</span> Field
        </button>
        <button onClick={() => handleInsertBlock('filter')}>
          <span className="icon">🔍</span> Filter
        </button>
        <button onClick={() => handleInsertBlock('aggregate')}>
          <span className="icon">Σ</span> Aggregate
        </button>
        <button onClick={() => handleInsertBlock('map')}>
          <span className="icon">🗺️</span> Map
        </button>
        <button onClick={() => handleInsertBlock('transform')}>
          <span className="icon">⚙️</span> Transform
        </button>
      </div>
      
      {/* Rich Text Editor */}
      <div 
        ref={editorRef}
        className="editor-content"
        contentEditable
        suppressContentEditableWarning
        onInput={(e) => {
          const text = e.currentTarget.textContent || '';
          handleTextChange(text);
        }}
        onSelect={() => {
          const selection = window.getSelection();
          if (selection) {
            setCursorPosition(selection.anchorOffset);
          }
        }}
      >
        {value.content.map((node, index) => {
          if (node.type === 'text') {
            return <span key={index}>{node.text}</span>;
          } else {
            return (
              <BlockComponent
                key={index}
                node={node}
                selected={selectedBlockIndex === index}
                onSelect={() => setSelectedBlockIndex(index)}
                onRemove={() => handleRemoveBlock(index)}
                onUpdate={(config) => handleUpdateBlock(index, config)}
              />
            );
          }
        })}
      </div>
      
      {/* Block Config Panel (when block selected) */}
      {selectedBlockIndex !== null && value.content[selectedBlockIndex].type === 'block' && (
        <BlockConfigPanel
          blockNode={value.content[selectedBlockIndex] as BlockNode}
          onUpdate={(config) => handleUpdateBlock(selectedBlockIndex, config)}
          onClose={() => setSelectedBlockIndex(null)}
        />
      )}
      
      {/* Raw Text View (toggle) */}
      <details className="raw-text-view">
        <summary>View Raw Text</summary>
        <textarea 
          value={value.rawText}
          onChange={(e) => handleTextChange(e.target.value)}
          className="raw-text-editor"
        />
      </details>
    </div>
  );
};

const BlockComponent: React.FC<{
  node: BlockNode;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onUpdate: (config: Record<string, any>) => void;
}> = ({ node, selected, onSelect, onRemove, onUpdate }) => {
  
  const getBlockIcon = (type: string) => {
    switch (type) {
      case 'field': return '📄';
      case 'filter': return '🔍';
      case 'aggregate': return 'Σ';
      case 'map': return '🗺️';
      case 'transform': return '⚙️';
      default: return '🧩';
    }
  };
  
  return (
    <span 
      className={`expression-block ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      contentEditable={false}
    >
      <span className="block-icon">{getBlockIcon(node.blockType)}</span>
      <span className="block-text">{node.displayText}</span>
      <button className="block-remove" onClick={onRemove}>×</button>
    </span>
  );
};

const BlockConfigPanel: React.FC<{
  blockNode: BlockNode;
  onUpdate: (config: Record<string, any>) => void;
  onClose: () => void;
}> = ({ blockNode, onUpdate, onClose }) => {
  
  const [config, setConfig] = useState(blockNode.config);
  
  const handleSave = () => {
    onUpdate(config);
    onClose();
  };
  
  return (
    <div className="block-config-panel">
      <div className="panel-header">
        <h4>Configure {blockNode.blockType}</h4>
        <button onClick={onClose}>×</button>
      </div>
      
      <div className="panel-body">
        {blockNode.blockType === 'field' && (
          <label>
            Path:
            <input 
              type="text"
              value={config.path || ''}
              onChange={(e) => setConfig({ ...config, path: e.target.value })}
            />
          </label>
        )}
        
        {blockNode.blockType === 'filter' && (
          <label>
            Condition:
            <input 
              type="text"
              value={config.condition || ''}
              onChange={(e) => setConfig({ ...config, condition: e.target.value })}
              placeholder="e.g., age > 18"
            />
          </label>
        )}
        
        {blockNode.blockType === 'aggregate' && (
          <>
            <label>
              Function:
              <select 
                value={config.function || 'sum'}
                onChange={(e) => setConfig({ ...config, function: e.target.value })}
              >
                <option value="sum">Sum</option>
                <option value="avg">Average</option>
                <option value="count">Count</option>
                <option value="min">Min</option>
                <option value="max">Max</option>
              </select>
            </label>
            <label>
              Path:
              <input 
                type="text"
                value={config.path || ''}
                onChange={(e) => setConfig({ ...config, path: e.target.value })}
              />
            </label>
          </>
        )}
        
        {blockNode.blockType === 'map' && (
          <label>
            Expression:
            <input 
              type="text"
              value={config.expression || ''}
              onChange={(e) => setConfig({ ...config, expression: e.target.value })}
              placeholder="e.g., name & ' ' & email"
            />
          </label>
        )}
        
        {blockNode.blockType === 'transform' && (
          <label>
            Operation:
            <select 
              value={config.operation || 'uppercase'}
              onChange={(e) => setConfig({ ...config, operation: e.target.value })}
            >
              <option value="uppercase">Uppercase</option>
              <option value="lowercase">Lowercase</option>
              <option value="trim">Trim</option>
              <option value="reverse">Reverse</option>
            </select>
          </label>
        )}
      </div>
      
      <div className="panel-footer">
        <button onClick={handleSave}>Save</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
};

function getDefaultBlockConfig(blockType: string): Record<string, any> {
  switch (blockType) {
    case 'field':
      return { path: '' };
    case 'filter':
      return { condition: '' };
    case 'aggregate':
      return { function: 'sum', path: '' };
    case 'map':
      return { expression: '' };
    case 'transform':
      return { operation: 'uppercase' };
    default:
      return {};
  }
}
```

## Sandboxed Compensation Handlers with Trust Levels

### Key Innovation: CSP-Based Sandboxing + Trust Verification

```typescript
type TrustLevel = 'system' | 'verified' | 'user' | 'untrusted';

interface CompensationHandlerConfig {
  id: string;
  name: string;
  trustLevel: TrustLevel;
  author?: string;
  verified?: boolean;
  
  handlerType: 'builtin' | 'http-api' | 'webhook' | 'custom';
  
  matches: {
    operation?: string[];
    description?: string[];
    service?: string[];
  };
  
  compensation: 
    | { type: 'http-api'; config: HttpApiConfig }
    | { type: 'webhook'; config: WebhookConfig }
    | { type: 'custom'; workerUrl: string }  // Sandboxed Web Worker
    | { type: 'manual'; steps: string[] };
}

interface HttpApiConfig {
  method: 'GET' | 'POST' | 'DELETE' | 'PUT';
  urlTemplate: string;
  allowedDomains: string[];  // Whitelist of domains this handler can call
  headers: Record<string, string>;
  bodyTemplate: string;
  auth?: {
    type: 'bearer' | 'basic' | 'api-key';
    tokenPath: string;
  };
}

interface WebhookConfig {
  url: string;
  allowedDomains: string[];
  method: 'POST' | 'PUT';
  payloadTemplate: string;
}

class SandboxedCompensationHandlerRegistry {
  private handlers: Map<string, CompensationHandler> = new Map();
  private configs: Map<string, CompensationHandlerConfig> = new Map();
  private trustedDomains: Set<string> = new Set(['api.stripe.com', 'hooks.slack.com']);
  
  // User approval tracking
  private approvedHandlers: Set<string> = new Set();
  
  constructor() {
    this.loadApprovedHandlers();
  }
  
  async registerFromConfig(
    config: CompensationHandlerConfig,
    requireApproval: boolean = true
  ): Promise<boolean> {
    
    // Check trust level
    if (requireApproval && config.trustLevel === 'untrusted') {
      const approved = await this.requestUserApproval(config);
      if (!approved) {
        return false;
      }
      this.approvedHandlers.add(config.id);
      this.persistApprovedHandlers();
    }
    
    // Validate config
    const validation = this.validateConfig(config);
    if (!validation.valid) {
      throw new Error(`Invalid handler config: ${validation.error}`);
    }
    
    this.configs.set(config.id, config);
    
    const handler = await this.createHandlerFromConfig(config);
    this.handlers.set(config.id, handler);
    
    return true;
  }
  
  private validateConfig(config: CompensationHandlerConfig): { valid: boolean; error?: string } {
    // Validate HTTP API config
    if (config.compensation.type === 'http-api') {
      const httpConfig = config.compensation.config;
      
      // Check URL against allowed domains
      const url = new URL(httpConfig.urlTemplate.replace(/\{\{[^}]+\}\}/g, 'placeholder'));
      
      if (!httpConfig.allowedDomains.includes(url.hostname)) {
        return {
          valid: false,
          error: `Domain ${url.hostname} not in allowedDomains list`
        };
      }
      
      // For untrusted handlers, require domain to be explicitly trusted
      if (config.trustLevel === 'untrusted' && !this.trustedDomains.has(url.hostname)) {
        return {
          valid: false,
          error: `Domain ${url.hostname} not in trusted domains list`
        };
      }
    }
    
    // Validate webhook config
    if (config.compensation.type === 'webhook') {
      const webhookConfig = config.compensation.config;
      const url = new URL(webhookConfig.url);
      
      if (!webhookConfig.allowedDomains.includes(url.hostname)) {
        return {
          valid: false,
          error: `Webhook domain ${url.hostname} not in allowedDomains list`
        };
      }
    }
    
    // Validate custom handler
    if (config.compensation.type === 'custom') {
      // Custom handlers must use data: URLs or trusted origins
      const workerUrl = config.compensation.workerUrl;
      
      if (!workerUrl.startsWith('data:') && !workerUrl.startsWith('blob:')) {
        return {
          valid: false,
          error: 'Custom handlers must use data: or blob: URLs for security'
        };
      }
    }
    
    return { valid: true };
  }
  
  private async requestUserApproval(
    config: CompensationHandlerConfig
  ): Promise<boolean> {
    
    return new Promise((resolve) => {
      // Show modal to user
      const modal = document.createElement('div');
      modal.className = 'approval-modal';
      modal.innerHTML = `
        <div class="modal-content">
          <h3>⚠️ Handler Approval Required</h3>
          <p>The handler "${config.name}" wants to perform compensations.</p>
          
          <div class="handler-details">
            <p><strong>Trust Level:</strong> ${config.trustLevel}</p>
            <p><strong>Author:</strong> ${config.author || 'Unknown'}</p>
            <p><strong>Type:</strong> ${config.compensation.type}</p>
            
            ${config.compensation.type === 'http-api' ? `
              <p><strong>Will call:</strong> ${config.compensation.config.urlTemplate}</p>
              <p><strong>Allowed domains:</strong> ${config.compensation.config.allowedDomains.join(', ')}</p>
            ` : ''}
            
            ${config.compensation.type === 'webhook' ? `
              <p><strong>Webhook URL:</strong> ${config.compensation.config.url}</p>
            ` : ''}
          </div>
          
          <p class="warning">This handler will be able to make HTTP requests on your behalf. Only approve if you trust the source.</p>
          
          <div class="modal-actions">
            <button id="approve-btn">Approve</button>
            <button id="deny-btn">Deny</button>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      modal.querySelector('#approve-btn')?.addEventListener('click', () => {
        document.body.removeChild(modal);
        resolve(true);
      });
      
      modal.querySelector('#deny-btn')?.addEventListener('click', () => {
        document.body.removeChild(modal);
        resolve(false);
      });
    });
  }
  
  private async createHandlerFromConfig(
    config: CompensationHandlerConfig
  ): Promise<CompensationHandler> {
    
    return {
      name: config.name,
      
      canHandle: (entry: SideEffectEntry) => {
        const { matches } = config;
        
        if (matches.operation && !matches.operation.includes(entry.operation)) {
          return false;
        }
        
        if (matches.description) {
          const descMatch = matches.description.some(pattern => 
            new RegExp(pattern).test(entry.description)
          );
          if (!descMatch) return false;
        }
        
        if (matches.service) {
          const descriptor = entry.compensation as any;
          if (!matches.service.includes(descriptor.service)) {
            return false;
          }
        }
        
        return true;
      },
      
      compensate: async (entry: SideEffectEntry) => {
        switch (config.compensation.type) {
          case 'http-api':
            return this.compensateViaHttpApi(entry, config.compensation.config, config.trustLevel);
            
          case 'webhook':
            return this.compensateViaWebhook(entry, config.compensation.config, config.trustLevel);
            
          case 'custom':
            return this.compensateViaCustomWorker(entry, config.compensation.workerUrl);
            
          case 'manual':
            return {
              success: false,
              requiresUserAction: true,
              manualSteps: config.compensation.steps
            };
            
          default:
            throw new Error(`Unknown compensation type`);
        }
      }
    };
  }
  
  private async compensateViaHttpApi(
    entry: SideEffectEntry,
    config: HttpApiConfig,
    trustLevel: TrustLevel
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    
    // Resolve URL
    const url = this.resolveTemplate(config.urlTemplate, {
      ...descriptor,
      effectId: entry.id
    });
    
    // Security check: Verify URL domain
    const urlObj = new URL(url);
    if (!config.allowedDomains.includes(urlObj.hostname)) {
      return {
        success: false,
        error: `Security: Domain ${urlObj.hostname} not allowed`,
        requiresUserAction: true,
        manualSteps: ['Manually compensate this effect', `URL attempted: ${url}`]
      };
    }
    
    // Build request
    const headers = { ...config.headers };
    
    if (config.auth) {
      const token = this.extractValue(descriptor, config.auth.tokenPath);
      switch (config.auth.type) {
        case 'bearer':
          headers['Authorization'] = `Bearer ${token}`;
          break;
        case 'api-key':
          headers['Authorization'] = token;
          break;
      }
    }
    
    const body = config.bodyTemplate
      ? this.resolveTemplate(config.bodyTemplate, descriptor)
      : undefined;
    
    try {
      const response = await fetch(url, {
        method: config.method,
        headers,
        body: body ? JSON.stringify(JSON.parse(body)) : undefined
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Compensated via ${config.method} ${url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        requiresUserAction: true,
        manualSteps: [
          `Failed to compensate via API: ${error.message}`,
          `Operation: ${entry.description}`,
          'Please manually revert'
        ]
      };
    }
  }
  
  private async compensateViaWebhook(
    entry: SideEffectEntry,
    config: WebhookConfig,
    trustLevel: TrustLevel
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    
    // Security check
    const urlObj = new URL(config.url);
    if (!config.allowedDomains.includes(urlObj.hostname)) {
      return {
        success: false,
        error: `Security: Webhook domain ${urlObj.hostname} not allowed`
      };
    }
    
    const payload = this.resolveTemplate(config.payloadTemplate, {
      ...descriptor,
      effectId: entry.id,
      effectDescription: entry.description
    });
    
    try {
      const response = await fetch(config.url, {
        method: config.method,
        headers: { 'Content-Type': 'application/json' },
        body: payload
      });
      
      if (!response.ok) {
        throw new Error(`Webhook failed: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Webhook triggered: ${config.url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  private async compensateViaCustomWorker(
    entry: SideEffectEntry,
    workerUrl: string
  ): Promise<CompensationResult> {
    
    return new Promise((resolve) => {
      const worker = new Worker(workerUrl);
      
      const timeout = setTimeout(() => {
        worker.terminate();
        resolve({
          success: false,
          error: 'Custom handler timeout'
        });
      }, 10000);
      
      worker.onmessage = (event) => {
        clearTimeout(timeout);
        worker.terminate();
        resolve(event.data);
      };
      
      worker.onerror = (error) => {
        clearTimeout(timeout);
        worker.terminate();
        resolve({
          success: false,
          error: `Worker error: ${error.message}`
        });
      };
      
      worker.postMessage({
        entry,
        descriptor: entry.compensation
      });
    });
  }
  
  private resolveTemplate(template: string, data: any): string {
    return template.replace(/\{\{([^}]+)\}\}/g, (_, path) => {
      return this.extractValue(data, path) ?? '';
    });
  }
  
  private extractValue(obj: any, path: string): any {
    const parts = path.split('.');
    let result = obj;
    for (const part of parts) {
      result = result?.[part];
    }
    return result;
  }
  
  private loadApprovedHandlers(): void {
    const stored = localStorage.getItem('approvedHandlers');
    if (stored) {
      this.approvedHandlers = new Set(JSON.parse(stored));
    }
  }
  
  private persistApprovedHandlers(): void {
    localStorage.setItem('approvedHandlers', JSON.stringify([...this.approvedHandlers]));
  }
  
  serializeConfigs(): CompensationHandlerConfig[] {
    return Array.from(this.configs.values());
  }
  
  loadConfigs(configs: CompensationHandlerConfig[]): void {
    for (const config of configs) {
      // Check if already approved
      const requireApproval = !this.approvedHandlers.has(config.id);
      this.registerFromConfig(config, requireApproval);
    }
  }
  
  unregister(id: string): void {
    this.handlers.delete(id);
    this.configs.delete(id);
    this.approvedHandlers.delete(id);
    this.persistApprovedHandlers();
  }
  
  findHandler(entry: SideEffectEntry): CompensationHandler | null {
    for (const handler of this.handlers.values()) {
      if (handler.canHandle(entry)) {
        return handler;
      }
    }
    return null;
  }
}

interface CompensationHandler {
  name: string;
  compensate(entry: SideEffectEntry): Promise<CompensationResult>;
  canHandle(entry: SideEffectEntry): boolean;
}

interface SideEffectEntry {
  id: string;
  nodeId: string;
  executionId: string;
  timestamp: number;
  operation: string;
  description: string;
  compensation: any;
  status: string;
}

interface CompensationResult {
  success: boolean;
  error?: string;
  message?: string;
  manualSteps?: string[];
  requiresUserAction?: boolean;
}
```

## Adaptive Performance Metrics with IndexedDB Persistence

### Key Innovation: Long-Term Analysis + Sampling Strategy

```typescript
interface MetricsConfig {
  enablePersistence: boolean;        // Store to IndexedDB
  samplingRate: number;              // 0.1 = 10% of measurements
  retentionDays: number;             // 7 days
  enableRecommendations: boolean;
}

interface StreamingMetrics {
  decisions: {
    teeCount: number;
    materializeCount: number;
    batchCount: number;
  };
  
  performance: {
    avgTeeMemory: number;
    avgMaterializeSize: number;
    avgTeeTime: number;
    avgMaterializeTime: number;
  };
  
  errors: {
    teeFailures: number;
    materializeFailures: number;
    storageFullErrors: number;
  };
  
  recommendations: {
    suggestedTeeThreshold: number;
    suggestedMaterializeThreshold: number;
    suggestedOverflowPolicy: string;
  };
}

interface Measurement {
  id: string;
  timestamp: number;
  strategy: 'tee' | 'materialize';
  sizeBytes: number;
  durationMs: number;
  memoryUsed: number;
  workflowId: string;
  nodeId: string;
}

class AdaptivePerformanceMonitor {
  private metrics: StreamingMetrics;
  private recentMeasurements: Measurement[] = [];
  private db: IDBDatabase | null = null;
  private config: MetricsConfig;
  
  constructor(config: MetricsConfig) {
    this.config = config;
    this.metrics = this.initMetrics();
    
    if (config.enablePersistence) {
      this.initDatabase();
    }
  }
  
  recordDecision(
    strategy: 'tee' | 'materialize' | 'batch',
    sizeBytes: number,
    durationMs: number,
    memoryUsed: number,
    context: {
      workflowId: string;
      nodeId: string;
    }
  ): void {
    
    switch (strategy) {
      case 'tee':
        this.metrics.decisions.teeCount++;
        break;
      case 'materialize':
        this.metrics.decisions.materializeCount++;
        break;
      case 'batch':
        this.metrics.decisions.batchCount++;
        break;
    }
    
    if (strategy === 'tee' || strategy === 'materialize') {
      // Apply sampling
      if (Math.random() < this.config.samplingRate) {
        const measurement: Measurement = {
          id: crypto.randomUUID(),
          timestamp: Date.now(),
          strategy,
          sizeBytes,
          durationMs,
          memoryUsed,
          workflowId: context.workflowId,
          nodeId: context.nodeId
        };
        
        this.recentMeasurements.push(measurement);
        
        // Keep last 100 in memory
        if (this.recentMeasurements.length > 100) {
          this.recentMeasurements.shift();
        }
        
        // Persist to IndexedDB
        if (this.config.enablePersistence && this.db) {
          this.persistMeasurement(measurement);
        }
      }
      
      this.updateAverages();
      
      if (this.config.enableRecommendations) {
        this.generateRecommendations();
      }
    }
  }
  
  recordError(type: 'tee' | 'materialize' | 'storage-full'): void {
    switch (type) {
      case 'tee':
        this.metrics.errors.teeFailures++;
        break;
      case 'materialize':
        this.metrics.errors.materializeFailures++;
        break;
      case 'storage-full':
        this.metrics.errors.storageFullErrors++;
        break;
    }
  }
  
  private updateAverages(): void {
    const tees = this.recentMeasurements.filter(m => m.strategy === 'tee');
    const materializes = this.recentMeasurements.filter(m => m.strategy === 'materialize');
    
    if (tees.length > 0) {
      this.metrics.performance.avgTeeMemory = 
        tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length;
      this.metrics.performance.avgTeeTime = 
        tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length;
    }
    
    if (materializes.length > 0) {
      this.metrics.performance.avgMaterializeSize = 
        materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length;
      this.metrics.performance.avgMaterializeTime = 
        materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length;
    }
  }
  
  private generateRecommendations(): void {
    // Tee threshold
    if (this.metrics.performance.avgTeeMemory > 10 * 1024 * 1024) {
      this.metrics.recommendations.suggestedTeeThreshold = 3 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedTeeThreshold = 5 * 1024 * 1024;
    }
    
    // Materialize threshold
    if (this.metrics.performance.avgMaterializeTime < 100) {
      this.metrics.recommendations.suggestedMaterializeThreshold = 100 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedMaterializeThreshold = 50 * 1024 * 1024;
    }
    
    // Overflow policy
    if (this.metrics.errors.storageFullErrors > 5) {
      this.metrics.recommendations.suggestedOverflowPolicy = 'evict-lru';
    } else {
      this.metrics.recommendations.suggestedOverflowPolicy = 'compress';
    }
  }
  
  async getHistoricalMetrics(
    workflowId?: string,
    startTime?: number,
    endTime?: number
  ): Promise<Measurement[]> {
    
    if (!this.config.enablePersistence || !this.db) {
      return this.recentMeasurements;
    }
    
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction('measurements', 'readonly');
      const store = tx.objectStore('measurements');
      const index = store.index('timestamp');
      
      const range = IDBKeyRange.bound(
        startTime || 0,
        endTime || Date.now()
      );
      
      const results: Measurement[] = [];
      const request = index.openCursor(range);
      
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result;
        if (cursor) {
          const measurement: Measurement = cursor.value;
          
          if (!workflowId || measurement.workflowId === workflowId) {
            results.push(measurement);
          }
          
          cursor.continue();
        } else {
          resolve(results);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }
  
  async generateReport(workflowId?: string): Promise<PerformanceReport> {
    const measurements = await this.getHistoricalMetrics(workflowId);
    
    const tees = measurements.filter(m => m.strategy === 'tee');
    const materializes = measurements.filter(m => m.strategy === 'materialize');
    
    return {
      totalMeasurements: measurements.length,
      timeRange: {
        start: Math.min(...measurements.map(m => m.timestamp)),
        end: Math.max(...measurements.map(m => m.timestamp))
      },
      strategies: {
        tee: {
          count: tees.length,
          avgMemory: tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length,
          avgDuration: tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length,
          avgSize: tees.reduce((sum, m) => sum + m.sizeBytes, 0) / tees.length
        },
        materialize: {
          count: materializes.length,
          avgMemory: materializes.reduce((sum, m) => sum + m.memoryUsed, 0) / materializes.length,
          avgDuration: materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length,
          avgSize: materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length
        }
      },
      recommendations: this.metrics.recommendations
    };
  }
  
  getMetrics(): StreamingMetrics {
    return { ...this.metrics };
  }
  
  getMeasurements(): Measurement[] {
    return [...this.recentMeasurements];
  }
  
  private async initDatabase(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('PerformanceMetrics', 2);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        this.cleanupOldMeasurements();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('measurements')) {
          const store = db.createObjectStore('measurements', { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
          store.createIndex('strategy', 'strategy', { unique: false });
        }
      };
    });
  }
  
  private async persistMeasurement(measurement: Measurement): Promise<void> {
    if (!this.db) return;
    
    const tx = this.db.transaction('measurements', 'readwrite');
    await tx.objectStore('measurements').add(measurement);
  }
  
  private async cleanupOldMeasurements(): Promise<void> {
    if (!this.db) return;
    
    const cutoff = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    
    const tx = this.db.transaction('measurements', 'readwrite');
    const store = tx.objectStore('measurements');
    const index = store.index('timestamp');
    
    const range = IDBKeyRange.upperBound(cutoff);
    const request = index.openCursor(range);
    
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
  }
  
  private initMetrics(): StreamingMetrics {
    return {
      decisions: {
        teeCount: 0,
        materializeCount: 0,
        batchCount: 0
      },
      performance: {
        avgTeeMemory: 0,
        avgMaterializeSize: 0,
        avgTeeTime: 0,
        avgMaterializeTime: 0
      },
      errors: {
        teeFailures: 0,
        materializeFailures: 0,
        storageFullErrors: 0
      },
      recommendations: {
        suggestedTeeThreshold: 5 * 1024 * 1024,
        suggestedMaterializeThreshold: 50 * 1024 * 1024,
        suggestedOverflowPolicy: 'evict-lru'
      }
    };
  }
}

interface PerformanceReport {
  totalMeasurements: number;
  timeRange: {
    start: number;
    end: number;
  };
  strategies: {
    tee: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
    };
    materialize: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
    };
  };
  recommendations: StreamingMetrics['recommendations'];
}
```

---