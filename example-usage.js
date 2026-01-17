// Example Usage of Authentication System

// This file demonstrates real-world usage scenarios

// ============ Scenario 1: Basic User Registration and Login ============
console.log('\n' + '='.repeat(60));
console.log('SCENARIO 1: User Registration and Login');
console.log('='.repeat(60));

const UserRepository = require('./test-runner.js');
const SessionRepository = require('./test-runner.js');
const TokenGenerator = require('./test-runner.js');
const PasswordHasher = require('./test-runner.js');
const AuthenticationService = require('./test-runner.js');

async function scenario1() {
  console.log('✓ Creating new user repository...');
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();

  // Create user
  const passwordHash = await hasher.hash('securePassword123!');
  const user = await userRepo.create({
    id: 'user-001',
    email: 'john.doe@example.com',
    passwordHash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true
  });
  console.log(`✓ User created: ${user.email}`);

  // Login
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);
  const loginResponse = await authService.login({
    email: 'john.doe@example.com',
    password: 'securePassword123!'
  });
  console.log(`✓ Login successful`);
  console.log(`  - Session ID: ${loginResponse.sessionId}`);
  console.log(`  - Token: ${loginResponse.token.substring(0, 20)}...`);
  console.log(`  - Expires at: ${loginResponse.expiresAt}`);

  // Validate session
  const validation = await authService.validateSession(loginResponse.token);
  console.log(`✓ Session validated for user: ${validation.userId}`);

  // Logout
  const logoutResponse = await authService.logout(loginResponse.sessionId);
  console.log(`✓ ${logoutResponse.message}`);
}

// ============ Scenario 2: Multiple Concurrent Sessions ============
console.log('\n' + '='.repeat(60));
console.log('SCENARIO 2: Multiple Concurrent Sessions');
console.log('='.repeat(60));

async function scenario2() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  // Create user
  const passwordHash = await hasher.hash('password456');
  const user = await userRepo.create({
    id: 'user-002',
    email: 'alice@example.com',
    passwordHash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true
  });
  console.log(`✓ User created: ${user.email}`);

  // Create multiple sessions (different devices/browsers)
  const session1 = await authService.login({
    email: 'alice@example.com',
    password: 'password456'
  });
  console.log(`✓ Session 1 created (Desktop): ${session1.sessionId}`);

  const session2 = await authService.login({
    email: 'alice@example.com',
    password: 'password456'
  });
  console.log(`✓ Session 2 created (Mobile): ${session2.sessionId}`);

  const session3 = await authService.login({
    email: 'alice@example.com',
    password: 'password456'
  });
  console.log(`✓ Session 3 created (Tablet): ${session3.sessionId}`);

  // Verify all sessions are active
  const val1 = await authService.validateSession(session1.token);
  const val2 = await authService.validateSession(session2.token);
  const val3 = await authService.validateSession(session3.token);
  console.log(`✓ All 3 sessions are active and valid`);

  // Logout from one session
  await authService.logout(session1.sessionId);
  console.log(`✓ Logged out from Session 1`);

  // Verify Session 1 is invalid, but others still work
  try {
    await authService.validateSession(session1.token);
    console.log(`✗ ERROR: Session 1 should be invalid`);
  } catch (error) {
    console.log(`✓ Session 1 is now invalid (as expected)`);
  }

  // Logout all sessions
  await authService.logoutAllSessions(user.id);
  console.log(`✓ All sessions for user logged out`);
}

// ============ Scenario 3: Error Handling ============
console.log('\n' + '='.repeat(60));
console.log('SCENARIO 3: Error Handling');
console.log('='.repeat(60));

async function scenario3() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  // Create user
  const passwordHash = await hasher.hash('correctPassword');
  await userRepo.create({
    id: 'user-003',
    email: 'bob@example.com',
    passwordHash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true
  });

  // Test 1: Wrong password
  try {
    await authService.login({
      email: 'bob@example.com',
      password: 'wrongPassword'
    });
  } catch (error) {
    console.log(`✓ Caught error: ${error.name} - ${error.message}`);
  }

  // Test 2: Non-existent user
  try {
    await authService.login({
      email: 'nonexistent@example.com',
      password: 'password'
    });
  } catch (error) {
    console.log(`✓ Caught error: ${error.name} - ${error.message}`);
  }

  // Test 3: Missing credentials
  try {
    await authService.login({
      email: '',
      password: ''
    });
  } catch (error) {
    console.log(`✓ Caught error: ${error.name} - ${error.message}`);
  }

  // Test 4: Invalid email format
  try {
    await authService.login({
      email: 'invalid-email-format',
      password: 'password'
    });
  } catch (error) {
    console.log(`✓ Caught error: ${error.name} - ${error.message}`);
  }
}

// ============ Scenario 4: Account Deactivation ============
console.log('\n' + '='.repeat(60));
console.log('SCENARIO 4: Account Deactivation');
console.log('='.repeat(60));

async function scenario4() {
  const userRepo = new UserRepository();
  const sessionRepo = new SessionRepository();
  const tokenGen = new TokenGenerator();
  const hasher = new PasswordHasher();
  const authService = new AuthenticationService(userRepo, sessionRepo, tokenGen, hasher);

  // Create and activate user
  const passwordHash = await hasher.hash('password789');
  const user = await userRepo.create({
    id: 'user-004',
    email: 'charlie@example.com',
    passwordHash,
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true
  });
  console.log(`✓ User created and active: ${user.email}`);

  // Login successfully
  const loginResponse = await authService.login({
    email: 'charlie@example.com',
    password: 'password789'
  });
  console.log(`✓ User logged in successfully`);

  // Deactivate account
  user.isActive = false;
  user.updatedAt = new Date();
  await userRepo.update(user);
  console.log(`✓ User account deactivated`);

  // Try to login with deactivated account
  try {
    await authService.login({
      email: 'charlie@example.com',
      password: 'password789'
    });
  } catch (error) {
    console.log(`✓ Login blocked for deactivated account: ${error.message}`);
  }
}

// ============ Run All Scenarios ============
async function runAllScenarios() {
  try {
    await scenario1();
  } catch (error) {
    console.error('Scenario 1 error:', error);
  }

  try {
    await scenario2();
  } catch (error) {
    console.error('Scenario 2 error:', error);
  }

  try {
    await scenario3();
  } catch (error) {
    console.error('Scenario 3 error:', error);
  }

  try {
    await scenario4();
  } catch (error) {
    console.error('Scenario 4 error:', error);
  }

  console.log('\n' + '='.repeat(60));
  console.log('All scenarios completed');
  console.log('='.repeat(60) + '\n');
}

// Run if executed directly
if (require.main === module) {
  runAllScenarios().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { runAllScenarios };
