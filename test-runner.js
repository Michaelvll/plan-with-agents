// Test Runner for Authentication System

// ============ Error Classes ============
class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ValidationError';
  }
}

class AuthenticationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AuthenticationError';
  }
}

class NotFoundError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NotFoundError';
  }
}

// ============ Repositories ============
class UserRepository {
  constructor() {
    this.users = new Map();
    this.emailIndex = new Map();
  }

  async findByEmail(email) {
    const userId = this.emailIndex.get(email);
    return userId ? this.users.get(userId) || null : null;
  }

  async findById(id) {
    return this.users.get(id) || null;
  }

  async create(user) {
    this.users.set(user.id, user);
    this.emailIndex.set(user.email, user.id);
    return user;
  }

  async update(user) {
    this.users.set(user.id, user);
    return user;
  }
}

class SessionRepository {
  constructor() {
    this.sessions = new Map();
    this.tokenIndex = new Map();
  }

  async findById(id) {
    return this.sessions.get(id) || null;
  }

  async findByToken(token) {
    const sessionId = this.tokenIndex.get(token);
    return sessionId ? this.sessions.get(sessionId) || null : null;
  }

  async create(session) {
    const id = Math.random().toString(36).substr(2, 9);
    const newSession = {
      id,
      ...session,
      createdAt: new Date()
    };
    this.sessions.set(id, newSession);
    this.tokenIndex.set(session.token, id);
    return newSession;
  }

  async delete(id) {
    const session = this.sessions.get(id);
    if (session) {
      this.tokenIndex.delete(session.token);
      this.sessions.delete(id);
    }
  }

  async findByUserId(userId) {
    return Array.from(this.sessions.values()).filter(s => s.userId === userId);
  }
}

// ============ Token Generator ============
class TokenGenerator {
  generate(userId) {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substr(2, 18);
    return `${userId}-${timestamp}-${random}`;
  }
}

// ============ Password Hasher ============
class PasswordHasher {
  async hash(password) {
    return `$hashed$${Buffer.from(password).toString('base64')}`;
  }

  async compare(password, hash) {
    const expectedHash = `$hashed$${Buffer.from(password).toString('base64')}`;
    return hash === expectedHash;
  }
}

// ============ Authentication Service ============
class AuthenticationService {
  constructor(userRepository, sessionRepository, tokenGenerator, passwordHasher) {
    this.userRepository = userRepository;
    this.sessionRepository = sessionRepository;
    this.tokenGenerator = tokenGenerator;
    this.passwordHasher = passwordHasher;
  }

  async login(request, ipAddress = '127.0.0.1', userAgent = 'test-agent') {
    if (!request.email || !request.password) {
      throw new ValidationError('Email and password are required');
    }

    if (!request.email.includes('@')) {
      throw new ValidationError('Invalid email format');
    }

    const user = await this.userRepository.findByEmail(request.email);
    if (!user) {
      throw new AuthenticationError('Invalid credentials');
    }

    const isPasswordValid = await this.passwordHasher.compare(
      request.password,
      user.passwordHash
    );
    if (!isPasswordValid) {
      throw new AuthenticationError('Invalid credentials');
    }

    if (!user.isActive) {
      throw new AuthenticationError('User account is disabled');
    }

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

  async logout(sessionId) {
    if (!sessionId) {
      throw new ValidationError('Session ID is required');
    }

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

  async validateSession(token) {
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

  async logoutAllSessions(userId) {
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

// ============ Test Utilities ============
async function createTestUser(repo, email, password) {
  const hasher = new PasswordHasher();
  const hash = await hasher.hash(password);
  return repo.create({
    id: `user-${Date.now()}`,
    email,
    passwordHash: hash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true
  });
}

// ============ Test Suites ============
const testResults = [];

async function testLoginSuccess() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  await createTestUser(userRepo, 'test@example.com', 'password123');

  try {
    const response = await authService.login({
      email: 'test@example.com',
      password: 'password123'
    });

    const passed =
      response.sessionId &&
      response.token &&
      response.user.email === 'test@example.com' &&
      response.expiresAt > new Date();

    testResults.push({ name: 'Login Success', passed });
  } catch (error) {
    testResults.push({ name: 'Login Success', passed: false, error: String(error) });
  }
}

async function testLoginInvalidEmail() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  try {
    await authService.login({
      email: 'nonexistent@example.com',
      password: 'password123'
    });
    testResults.push({ name: 'Login Invalid Email', passed: false, error: 'Should have thrown AuthenticationError' });
  } catch (error) {
    const passed = error instanceof AuthenticationError;
    testResults.push({ name: 'Login Invalid Email', passed });
  }
}

async function testLoginWrongPassword() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  await createTestUser(userRepo, 'test@example.com', 'password123');

  try {
    await authService.login({
      email: 'test@example.com',
      password: 'wrongpassword'
    });
    testResults.push({ name: 'Login Wrong Password', passed: false, error: 'Should have thrown AuthenticationError' });
  } catch (error) {
    const passed = error instanceof AuthenticationError;
    testResults.push({ name: 'Login Wrong Password', passed });
  }
}

async function testLoginMissingEmail() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  try {
    await authService.login({
      email: '',
      password: 'password123'
    });
    testResults.push({ name: 'Login Missing Email', passed: false, error: 'Should have thrown ValidationError' });
  } catch (error) {
    const passed = error instanceof ValidationError;
    testResults.push({ name: 'Login Missing Email', passed });
  }
}

async function testLogoutSuccess() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  await createTestUser(userRepo, 'test@example.com', 'password123');
  const loginResponse = await authService.login({
    email: 'test@example.com',
    password: 'password123'
  });

  try {
    const response = await authService.logout(loginResponse.sessionId);
    const passed = response.success === true && response.message.includes('logged out');
    testResults.push({ name: 'Logout Success', passed });
  } catch (error) {
    testResults.push({ name: 'Logout Success', passed: false, error: String(error) });
  }
}

async function testLogoutInvalidSession() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  try {
    await authService.logout('nonexistent-session-id');
    testResults.push({ name: 'Logout Invalid Session', passed: false, error: 'Should have thrown NotFoundError' });
  } catch (error) {
    const passed = error instanceof NotFoundError;
    testResults.push({ name: 'Logout Invalid Session', passed });
  }
}

async function testValidateSessionSuccess() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  const user = await createTestUser(userRepo, 'test@example.com', 'password123');
  const loginResponse = await authService.login({
    email: 'test@example.com',
    password: 'password123'
  });

  try {
    const validation = await authService.validateSession(loginResponse.token);
    const passed = validation.userId === user.id;
    testResults.push({ name: 'Validate Session Success', passed });
  } catch (error) {
    testResults.push({ name: 'Validate Session Success', passed: false, error: String(error) });
  }
}

async function testValidateInvalidToken() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  try {
    await authService.validateSession('invalid-token');
    testResults.push({ name: 'Validate Invalid Token', passed: false, error: 'Should have thrown AuthenticationError' });
  } catch (error) {
    const passed = error instanceof AuthenticationError;
    testResults.push({ name: 'Validate Invalid Token', passed });
  }
}

async function testDisabledUserLogin() {
  const userRepo = new UserRepository();
  const hasher = new PasswordHasher();
  const hash = await hasher.hash('password123');

  await userRepo.create({
    id: 'user-disabled',
    email: 'disabled@example.com',
    passwordHash: hash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: false
  });

  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  try {
    await authService.login({
      email: 'disabled@example.com',
      password: 'password123'
    });
    testResults.push({ name: 'Disabled User Login', passed: false, error: 'Should have thrown AuthenticationError' });
  } catch (error) {
    const passed = error instanceof AuthenticationError && error.message.includes('disabled');
    testResults.push({ name: 'Disabled User Login', passed });
  }
}

async function testLogoutAllSessions() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  const user = await createTestUser(userRepo, 'test@example.com', 'password123');

  await authService.login({
    email: 'test@example.com',
    password: 'password123'
  });
  await authService.login({
    email: 'test@example.com',
    password: 'password123'
  });

  try {
    const response = await authService.logoutAllSessions(user.id);
    const passed = response.success === true;
    testResults.push({ name: 'Logout All Sessions', passed });
  } catch (error) {
    testResults.push({ name: 'Logout All Sessions', passed: false, error: String(error) });
  }
}

// ============ Run All Tests ============
async function runAllTests() {
  await testLoginSuccess();
  await testLoginInvalidEmail();
  await testLoginWrongPassword();
  await testLoginMissingEmail();
  await testLogoutSuccess();
  await testLogoutInvalidSession();
  await testValidateSessionSuccess();
  await testValidateInvalidToken();
  await testDisabledUserLogin();
  await testLogoutAllSessions();
}

// ============ Main Execution ============
(async () => {
  await runAllTests();

  const passed = testResults.filter(t => t.passed).length;
  const total = testResults.length;
  const percentage = Math.round((passed / total) * 100);

  console.log('\n' + '='.repeat(60));
  console.log('AUTHENTICATION SYSTEM TEST REPORT');
  console.log('='.repeat(60));

  testResults.forEach(result => {
    const status = result.passed ? '✓ PASS' : '✗ FAIL';
    console.log(`${status}: ${result.name}`);
    if (result.error) {
      console.log(`       ${result.error}`);
    }
  });

  console.log('='.repeat(60));
  console.log(`TOTAL: ${passed}/${total} tests passed (${percentage}%)`);
  console.log('='.repeat(60));
  console.log('');

  if (percentage === 100) {
    console.log('✓ All tests passed! System is ready for integration testing.');
  } else {
    console.log(`✗ ${total - passed} test(s) failed. Issues need to be addressed.`);
  }

  process.exit(percentage === 100 ? 0 : 1);
})().catch(error => {
  console.error('Test runner error:', error);
  process.exit(1);
});
