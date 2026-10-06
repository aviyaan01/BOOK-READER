---
name: coderabbit
description: >-
  Performs in-depth, automated AI code review and pull request analysis modeled after CodeRabbit. Use when reviewing code changes, auditing pull requests, identifying security vulnerabilities, detecting performance regressions, checking architectural patterns, and ensuring robust test coverage.
license: Apache-2.0
metadata:
  version: v1.0.0
  author: CodeRabbit AI
---

# CodeRabbit Code Review Protocol

CodeRabbit provides thorough, context-aware code review and pull request analysis. It identifies subtle bugs, security vulnerabilities, performance anti-patterns, and architectural regressions before code merges into production.

---

## 1. Review Dimensions

When conducting a CodeRabbit review, evaluate changes across the following core dimensions:

### 1. Correctness & Logic
- **Edge Cases**: Empty lists, null/None values, zero division, boundary conditions.
- **Concurrency & State**: Race conditions, deadlock potentials, thread safety, state mutability.
- **Error Handling**: Proper propagation vs. silent swallows, descriptive error messages, cleanup in finally/defer blocks.

### 2. Security & Compliance
- **Injection Flaws**: SQL injection, command execution, path traversal, template injection.
- **Authentication & Authorization**: Missing permissions, privilege escalation, token validation.
- **Sensitive Data**: Hardcoded secrets, API keys, credentials, PII leakage in logs.
- **Data Validation & Sanitization**: Strict input validation, schema enforcement, safe deserialization.

### 3. Performance & Resource Efficiency
- **Database & Queries**: N+1 query patterns, missing indexes, missing query limits/pagination.
- **Memory & Lifecycle**: Unbounded caches, leaked file handles or database connections, memory retention.
- **Algorithmic Complexity**: Unnecessary nested loops, suboptimal data structures.

### 4. Architecture & Maintainability
- **Modularity & Coupling**: Single Responsibility Principle, separation of concerns, clean interface boundaries.
- **API & Backward Compatibility**: Breaking changes in contracts, schema migrations, graceful deprecations.
- **Readability & Standards**: Idiomatic code for the given language, clear naming, appropriate documentation.

### 5. Test Coverage & Quality
- **Coverage**: Are new features and edge cases covered by automated tests?
- **Test Integrity**: Do tests assert behavior or merely exercise code lines?
- **Mocking**: Are external dependencies properly isolated without over-mocking business logic?

---

## 2. Severity Classification

Every review finding must be categorized with an explicit severity level:

| Tag | Level | Description | Action Required |
| :--- | :--- | :--- | :--- |
| 🔴 **[CRITICAL]** | Blocker | Bugs causing crashes, data loss, security vulnerabilities, or build failures. | Must fix before merge. |
| 🟠 **[MAJOR]** | High | Architectural issues, missing error boundaries, significant performance degradation. | Strong recommendation to fix. |
| 🟡 **[MINOR]** | Medium | Non-critical edge cases, sub-optimal implementations, missing unit tests. | Should address if feasible. |
| 💡 **[SUGGESTION]** | Low / Nit | Code readability, minor idioms, documentation, style improvements. | Optional / Informational. |

---

## 3. Review Output Format

Structure the review response cleanly:

```markdown
# 🐇 CodeRabbit Review Summary

### Executive Summary
[High-level overview of what the changes accomplish and overall risk assessment]

### 🔍 Walkthrough
- `path/to/file1.py`: [Summary of changes in this file]
- `path/to/file2.ts`: [Summary of changes in this file]

---

### 📋 Findings & Recommendations

#### 🔴 [CRITICAL] Potential Null Pointer Exception in `UserService`
- **Location**: [`src/services/user.py:42-45`](file:///src/services/user.py#L42-L45)
- **Problem**: When `get_user_by_id()` returns `None`, calling `.profile` raises `AttributeError`.
- **Recommendation**:
```diff
- return user.profile.email
+ if not user or not user.profile:
+     return None
+ return user.profile.email
```

---

### ✅ Checklist
- [x] Security review passed (no leaks, sanitized inputs)
- [x] Core logic verified
- [ ] Test coverage added for new edge cases
```
