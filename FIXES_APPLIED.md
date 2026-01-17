# Fixes Applied to Plan-with-Debate System

## Date: 2026-01-17

## Problem Identified

The debate system had agents that were violating format requirements by including argumentative preambles before the `## Design` section. Example from `debate_output/session_20260116_221850/final_design.md`:

```markdown
You've caught legitimate bugs in my implementation - I respect that. But your "fixes" introduce MORE complexity than necessary.

## Design

# E-Commerce Order Schema - ARCHITECT Response (Round 5)
...
```

This violated the intended format where designs should start immediately with `## Design` and contain no meta-commentary or debate artifacts.

## Root Cause

1. **Weak system prompt enforcement**: While the prompts mentioned format requirements, they weren't emphatic enough
2. **No validation**: Responses were accepted without checking format compliance
3. **No user feedback**: Format violations were silently propagated to final designs

## Fixes Applied

### 1. Strengthened System Prompts

**For Both Agents (A and B):**

Added prominent warning at the very top:
```
🚨 CRITICAL FORMAT REQUIREMENT 🚨
YOUR VERY FIRST LINE MUST BE: ## Design

DO NOT write ANYTHING before "## Design" - no preamble, no commentary, no responses to feedback.
```

Added explicit FORBIDDEN behaviors:
- ❌ Responses to the other agent's critiques
- ❌ Argumentative statements
- ❌ Commentary about what you're doing
- ❌ Preambles or introductions
- ❌ Reading confirmations

Added concrete examples of CORRECT vs WRONG format with visual examples.

**Files Modified:** `debate` (lines 924-1082)

### 2. Added Response Validation

Created `validate_response_format()` function that:
- Checks if response starts with `## Design` (after stripping whitespace)
- Detects preambles and reports them with line numbers
- Provides actionable error messages

**Files Modified:** `debate` (lines 1399-1427)

### 3. Integrated Validation into Debate Loop

Added validation calls after each agent response:
- Validates Agent A's response after generation
- Validates Agent B's response after generation
- Displays warnings when format violations are detected
- Warnings are shown in yellow color for visibility

**Files Modified:** `debate` (lines 1629-1632, 1678-1681)

### 4. Improved extract_design_section()

Enhanced to strip adversarial preambles automatically:
- Looks for `## Design` marker and starts from there
- Ignores any text before the Design section
- Falls back gracefully if no Design section found

**Files Modified:** `debate` (lines 1430-1488)

## Verification

Created `test_validation.py` to verify the fix works:

```bash
$ python3 test_validation.py
============================================================
Testing Format Validation
============================================================

✓ PASS: Good format - starts with ## Design
✓ PASS: Bad format - preamble before Design
✓ PASS: Bad format - commentary before Design
✓ PASS: Good format - minimal whitespace before Design
✓ PASS: Bad format - argumentative preamble

============================================================
Results: 5 passed, 0 failed
============================================================

✓ All tests passed! Format validation is working correctly.
```

## Expected Impact

1. **Cleaner final designs**: No more argumentative preambles in final outputs
2. **Better agent behavior**: Stronger prompts should reduce format violations
3. **User visibility**: Warnings alert users when agents violate format (though extraction will still clean it up)
4. **Automatic recovery**: Even if agents violate format, the extractor strips preambles

## Testing Next Steps

1. Run debate on simple tasks (CRUD API, todo list, etc.)
2. Check final_design.md files for format compliance
3. Verify no preambles appear before ## Design
4. Test with max-iterations to ensure consistency

## Files Changed

- `debate` (main script)
  - System prompts strengthened (lines 924-1082)
  - Validation function added (lines 1399-1427)
  - Validation integrated into debate loop (lines 1629-1632, 1678-1681)
  - Design extraction improved (lines 1430-1488)

## Files Created

- `test_validation.py` - Unit tests for format validation
- `test_debate.sh` - Integration test script
- `FIXES_APPLIED.md` - This document

## Backward Compatibility

✅ No breaking changes
✅ Existing sessions remain unchanged
✅ Old prompts replaced with new ones
✅ Validation is warning-only (doesn't block)
✅ Extraction handles both clean and dirty responses

## Success Criteria

The fix is successful when:
- [ ] No preambles appear in final_design.md files
- [ ] Agents consistently start responses with ## Design
- [ ] Format warnings appear for violations (in terminal output)
- [ ] Final designs are clean, professional documents
- [ ] Can run 10 iterations without format regressions
