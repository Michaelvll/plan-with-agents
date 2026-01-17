// Test Runner

import { generateReport } from './auth-system.test';

(async () => {
  const report = await generateReport();
  process.exit(report.percentage === 100 ? 0 : 1);
})().catch(error => {
  console.error('Test runner error:', error);
  process.exit(1);
});
