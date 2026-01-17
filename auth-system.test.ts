// Unit Tests for Authentication System

import {
  AuthenticationService,
  UserRepository,
  SessionRepository,
  TokenGenerator,
  PasswordHasher,
  ValidationError,
  AuthenticationError,
  NotFoundError,
  User
} from './auth-system';

// ============ Test Utilities ============
async function createTestUser(repo: UserRepository, email: string, password: string): Promise<User> {
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
const testResults: { name: string; passed: boolean; error?: string }[] = [];

// Test Suite 1: Login Success
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

// Test Suite 2: Login with Invalid Email
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

// Test Suite 3: Login with Wrong Password
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

// Test Suite 4: Login Missing Email
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

// Test Suite 5: Logout Success
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

// Test Suite 6: Logout Invalid Session
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

// Test Suite 7: Validate Session Success
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

// Test Suite 8: Validate Invalid Token
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

// Test Suite 9: Disabled User Login
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

// Test Suite 10: Logout All Sessions
async function testLogoutAllSessions() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  const user = await createTestUser(userRepo, 'test@example.com', 'password123');

  // Create two sessions
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

// ============ Test Report ============
async function generateReport() {
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

  return { passed, total, percentage, results: testResults };
}

export { generateReport };
