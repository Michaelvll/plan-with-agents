// Express.js Integration Example for Authentication System

import express, { Request, Response, NextFunction } from 'express';
import {
  AuthenticationService,
  UserRepository,
  SessionRepository,
  TokenGenerator,
  PasswordHasher,
  ValidationError,
  AuthenticationError,
  NotFoundError
} from './auth-system';

// ============ Express Middleware ============

// Extend Express Request to include authenticated user
declare global {
  namespace Express {
    interface Request {
      userId?: string;
      sessionId?: string;
    }
  }
}

// Authentication middleware
function authMiddleware(authService: AuthenticationService) {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const token = req.headers.authorization?.split(' ')[1];
      if (!token) {
        return res.status(401).json({ error: 'Missing authorization token' });
      }

      const validation = await authService.validateSession(token);
      req.userId = validation.userId;
      next();
    } catch (error) {
      res.status(401).json({ error: 'Invalid or expired token' });
    }
  };
}

// ============ Controller ============
class AuthController {
  constructor(
    private authService: AuthenticationService,
    private userRepository: UserRepository,
    private passwordHasher: PasswordHasher
  ) {}

  async register(req: Request, res: Response) {
    try {
      const { email, password, confirmPassword } = req.body;

      // Validation
      if (!email || !password) {
        return res.status(400).json({ error: 'Email and password are required' });
      }

      if (password !== confirmPassword) {
        return res.status(400).json({ error: 'Passwords do not match' });
      }

      if (password.length < 8) {
        return res.status(400).json({ error: 'Password must be at least 8 characters' });
      }

      // Check if user exists
      const existingUser = await this.userRepository.findByEmail(email);
      if (existingUser) {
        return res.status(400).json({ error: 'User with this email already exists' });
      }

      // Create user
      const passwordHash = await this.passwordHasher.hash(password);
      const user = await this.userRepository.create({
        id: `user-${Date.now()}`,
        email,
        passwordHash,
        createdAt: new Date(),
        updatedAt: new Date(),
        isActive: true
      });

      res.status(201).json({
        message: 'User registered successfully',
        user: { id: user.id, email: user.email }
      });
    } catch (error) {
      this.handleError(error, res);
    }
  }

  async login(req: Request, res: Response) {
    try {
      const { email, password } = req.body;

      const response = await this.authService.login({
        email,
        password
      });

      // Set secure HTTP-only cookie for token
      res.cookie('auth_token', response.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: 24 * 60 * 60 * 1000 // 24 hours
      });

      res.status(200).json({
        sessionId: response.sessionId,
        user: response.user,
        expiresAt: response.expiresAt,
        message: 'Login successful'
      });
    } catch (error) {
      this.handleError(error, res);
    }
  }

  async logout(req: Request, res: Response) {
    try {
      const sessionId = req.headers['x-session-id'] as string;

      if (!sessionId) {
        return res.status(400).json({ error: 'Session ID is required' });
      }

      const response = await this.authService.logout(sessionId);

      // Clear cookie
      res.clearCookie('auth_token');

      res.status(200).json(response);
    } catch (error) {
      this.handleError(error, res);
    }
  }

  async validateToken(req: Request, res: Response) {
    try {
      const token = req.headers.authorization?.split(' ')[1];

      if (!token) {
        return res.status(400).json({ error: 'Token is required' });
      }

      const validation = await this.authService.validateSession(token);

      res.status(200).json({
        valid: true,
        userId: validation.userId
      });
    } catch (error) {
      res.status(401).json({ valid: false, error: 'Token is invalid or expired' });
    }
  }

  async getProfile(req: Request, res: Response) {
    try {
      if (!req.userId) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const user = await this.userRepository.findById(req.userId);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }

      res.status(200).json({
        id: user.id,
        email: user.email,
        createdAt: user.createdAt
      });
    } catch (error) {
      this.handleError(error, res);
    }
  }

  private handleError(error: Error, res: Response) {
    if (error instanceof ValidationError) {
      res.status(400).json({ error: error.message });
    } else if (error instanceof AuthenticationError) {
      res.status(401).json({ error: error.message });
    } else if (error instanceof NotFoundError) {
      res.status(404).json({ error: error.message });
    } else {
      res.status(500).json({ error: 'Internal server error' });
    }
  }
}

// ============ Express App Setup ============
export function setupAuthRoutes(app: express.Application) {
  // Initialize dependencies
  const userRepository = new UserRepository();
  const sessionRepository = new SessionRepository();
  const tokenGenerator = new TokenGenerator();
  const passwordHasher = new PasswordHasher();
  const authService = new AuthenticationService(
    userRepository,
    sessionRepository,
    tokenGenerator,
    passwordHasher
  );

  const controller = new AuthController(authService, userRepository, passwordHasher);

  // Routes
  app.post('/auth/register', (req, res) => controller.register(req, res));
  app.post('/auth/login', (req, res) => controller.login(req, res));
  app.post('/auth/logout', (req, res) => controller.logout(req, res));
  app.post('/auth/validate', (req, res) => controller.validateToken(req, res));

  // Protected route example
  app.get(
    '/auth/profile',
    authMiddleware(authService),
    (req, res) => controller.getProfile(req, res)
  );

  return { authService, userRepository, sessionRepository };
}

// ============ Example Usage ============
export async function startExampleServer() {
  const app = express();
  app.use(express.json());

  setupAuthRoutes(app);

  const PORT = process.env.PORT || 3000;

  app.listen(PORT, () => {
    console.log(`✓ Auth server running on port ${PORT}`);
    console.log('\nAvailable endpoints:');
    console.log('  POST   /auth/register    - Register new user');
    console.log('  POST   /auth/login       - Login user');
    console.log('  POST   /auth/logout      - Logout user');
    console.log('  POST   /auth/validate    - Validate token');
    console.log('  GET    /auth/profile     - Get user profile (protected)');
  });

  return app;
}

// ============ Example Requests ============
/*
# Register User
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "confirmPassword": "SecurePassword123"
}

# Login
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123"
}

# Validate Token
POST /auth/validate
Authorization: Bearer {token}

# Get Profile (Protected)
GET /auth/profile
Authorization: Bearer {token}

# Logout
POST /auth/logout
X-Session-Id: {sessionId}
*/
