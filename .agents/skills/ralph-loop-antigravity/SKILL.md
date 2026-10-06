---
name: ralph-loop-antigravity
description: >-
  Implements the Ralph autonomous feedback loop protocol for Antigravity. Use when a task requires an iterative, self-correcting test-driven loop—proposing fixes, running tests, analyzing failures, and auto-correcting repeatedly without stopping prematurely until all verification criteria pass.
license: MIT
metadata:
  version: v1.1.0
  author: Ralph Loop Community
---

# Ralph Loop for Antigravity

The Ralph Loop is an autonomous, self-correcting execution loop designed for test-driven development, bug fixing, and continuous verification. Rather than stopping after a single attempt or asking premature questions, the agent iterates relentlessly through a test-analyze-fix cycle until the code passes all checks.

---

## 1. Loop Architecture

```
     ┌────────────────────────────────────────────────────────┐
     │                                                        │
     ▼                                                        │
[1. Hypothesize] ──► [2. Surgical Patch] ──► [3. Run Tests] ──┘ (If tests fail)
                                                    │
                                                    ▼ (If all tests pass)
                                         [4. Regression Check]
                                                    │
                                                    ▼ (Green)
                                              [5. Complete]
```

---

## 2. The Ralph Protocol Rules

1. **Autonomous Persistence**:
   - When a test fails or an error is raised, do **not** stop and ask "Would you like me to fix this?".
   - Immediately enter the next iteration of the loop, diagnose the error, apply a fix, and rerun the test.

2. **Root-Cause Anchoring**:
   - Never suppress errors with catch-all handlers (`except: pass`, `@ts-ignore`) unless explicitly requested.
   - Trace the exact stack trace and fix the root cause in the underlying logic.

3. **Minimal Surgical Changes**:
   - Each iteration must introduce targeted, minimal edits so causality remains clear.
   - If a change causes a regression in a previously passing test, revert or adjust immediately.

4. **Circuit Breakers (Anti-Thrashing)**:
   - **Oscillation Detection**: If you find yourself toggling between two alternative implementations, pause and inspect the architectural contract.
   - **Max Iterations**: If the issue is not resolved within 5-7 iterations, step back, re-read the core requirements, or provide a clear diagnosis of conflicting constraints.

---

## 3. Step-by-Step Ralph Loop Execution

### Step 1: Baseline Assessment
- Run the existing test suite or verification command:
  ```bash
  pytest backend/tests/
  npm test
  cargo test
  ```
- Identify all failing test cases and capture the exact failure messages.

### Step 2: Formulate Hypothesis
- Analyze the traceback, line numbers, and expected vs. actual values.
- Formulate a clear hypothesis: *"The function fails because it expects a dictionary but receives None when the query yields no rows."*

### Step 3: Implement Surgical Fix
- Use `replace_file_content` to apply the targeted fix.
- Ensure the fix handles edge cases (e.g., empty strings, null values, network timeouts).

### Step 4: Re-Test Immediately
- Execute the specific failing test first for rapid feedback.
- If it passes, run the full test suite to guarantee zero regressions.

### Step 5: Verification & Exit Criteria
- The loop exits **only** when:
  1. All target tests pass green (exit code 0).
  2. No existing tests are broken.
  3. Code formatting and linting pass cleanly.
