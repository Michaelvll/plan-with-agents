// Authentication System Implementation

// ============ Error Classes ============
class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

class AuthenticationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthenticationError';
  }
}

class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NotFoundError';
  }
}

// ============ Data Models ============
interface User {
  id: string;
  email: string;
  passwordHash: string;
  createdAt: Date;
  updatedAt: Date;
  isActive: boolean;
}

interface Session {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
  createdAt: Date;
  ipAddress: string;
  userAgent: string;
}

interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  sessionId: string;
  token: string;
  user: {
    id: string;
    email: string;
  };
  expiresAt: Date;
}

interface LogoutResponse {
  success: boolean;
  message: string;
}

// ============ Repositories ============
class UserRepository {
  private users: Map<string, User> = new Map();
  private emailIndex: Map<string, string> = new Map();

  async findByEmail(email: string): Promise<User | null> {
    const userId = this.emailIndex.get(email);
    return userId ? this.users.get(userId) || null : null;
  }

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async create(user: User): Promise<User> {
    this.users.set(user.id, user);
    this.emailIndex.set(user.email, user.id);
    return user;
  }

  async update(user: User): Promise<User> {
    this.users.set(user.id, user);
    return user;
  }
}

class SessionRepository {
  private sessions: Map<string, Session> = new Map();
  private tokenIndex: Map<string, string> = new Map();

  async findById(id: string): Promise<Session | null> {
    return this.sessions.get(id) || null;
  }

  async findByToken(token: string): Promise<Session | null> {
    const sessionId = this.tokenIndex.get(token);
    return sessionId ? this.sessions.get(sessionId) || null : null;
  }

  async create(session: Omit<Session, 'id' | 'createdAt'>): Promise<Session> {
    const id = Math.random().toString(36).substr(2, 9);
    const newSession: Session = {
      id,
      ...session,
      createdAt: new Date()
    };
    this.sessions.set(id, newSession);
    this.tokenIndex.set(session.token, id);
    return newSession;
  }

  async delete(id: string): Promise<void> {
    const session = this.sessions.get(id);
    if (session) {
      this.tokenIndex.delete(session.token);
      this.sessions.delete(id);
    }
  }

  async findByUserId(userId: string): Promise<Session[]> {
    return Array.from(this.sessions.values()).filter(s => s.userId === userId);
  }
}

// ============ Token Generator ============
class TokenGenerator {
  generate(userId: string): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substr(2, 18);
    return `${userId}-${timestamp}-${random}`;
  }
}

// ============ Password Hasher ============
class PasswordHasher {
  async hash(password: string): Promise<string> {
    // Simplified hash for demo (in production use bcrypt)
    return `$hashed$${Buffer.from(password).toString('base64')}`;
  }

  async compare(password: string, hash: string): Promise<boolean> {
    const expectedHash = `$hashed$${Buffer.from(password).toString('base64')}`;
    return hash === expectedHash;
  }
}

// ============ Authentication Service ============
class AuthenticationService {
  constructor(
    private userRepository: UserRepository,
    private sessionRepository: SessionRepository,
    private tokenGenerator: TokenGenerator,
    private passwordHasher: PasswordHasher
  ) {}

  async login(request: LoginRequest, ipAddress: string = '127.0.0.1', userAgent: string = 'test-agent'): Promise<LoginResponse> {
    // Validate input
    if (!request.email || !request.password) {
      throw new ValidationError('Email and password are required');
    }

    if (!request.email.includes('@')) {
      throw new ValidationError('Invalid email format');
    }

    // Find user
    const user = await this.userRepository.findByEmail(request.email);
    if (!user) {
      throw new AuthenticationError('Invalid credentials');
    }

    // Verify password
    const isPasswordValid = await this.passwordHasher.compare(
      request.password,
      user.passwordHash
    );
    if (!isPasswordValid) {
      throw new AuthenticationError('Invalid credentials');
    }

    // Check user is active
    if (!user.isActive) {
      throw new AuthenticationError('User account is disabled');
    }

    // Generate session and token
    const token = this.tokenGenerator.generate(user.id);
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + 24);

    const session = await this.sessionRepository.create({
      userId: user.id,
      token,
      expiresAt,
      ipAddress,
      userAgent
    });

    return {
      sessionId: session.id,
      token: session.token,
      user: {
        id: user.id,
        email: user.email
      },
      expiresAt: session.expiresAt
    };
  }

  async logout(sessionId: string): Promise<LogoutResponse> {
    // Validate input
    if (!sessionId) {
      throw new ValidationError('Session ID is required');
    }

    // Find and delete session
    const session = await this.sessionRepository.findById(sessionId);
    if (!session) {
      throw new NotFoundError('Session not found');
    }

    await this.sessionRepository.delete(sessionId);

    return {
      success: true,
      message: 'Successfully logged out'
    };
  }

  async validateSession(token: string): Promise<{ userId: string }> {
    if (!token) {
      throw new ValidationError('Token is required');
    }

    const session = await this.sessionRepository.findByToken(token);

    if (!session) {
      throw new AuthenticationError('Session not found');
    }

    if (new Date() > session.expiresAt) {
      await this.sessionRepository.delete(session.id);
      throw new AuthenticationError('Session expired');
    }

    return { userId: session.userId };
  }

  async logoutAllSessions(userId: string): Promise<LogoutResponse> {
    const sessions = await this.sessionRepository.findByUserId(userId);
    for (const session of sessions) {
      await this.sessionRepository.delete(session.id);
    }
    return {
      success: true,
      message: `Successfully logged out from ${sessions.length} session(s)`
    };
  }
}

// ============ Export for testing ============
export {
  AuthenticationService,
  UserRepository,
  SessionRepository,
  TokenGenerator,
  PasswordHasher,
  ValidationError,
  AuthenticationError,
  NotFoundError,
  User,
  Session,
  LoginRequest,
  LoginResponse,
  LogoutResponse
};
