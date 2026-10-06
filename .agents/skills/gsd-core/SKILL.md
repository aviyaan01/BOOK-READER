---
name: gsd-core
description: >-
  Executes tasks with the Get-Stuff-Done (GSD) structured framework. Use when tackling complex, multi-step engineering tasks requiring rigorous task decomposition, milestone tracking, scratchpad maintenance, and systematic verification before completion.
license: MIT
metadata:
  version: v1.0.0
  author: GSD Community
---

# GSD Core (Get Stuff Done)

GSD Core is a high-velocity, structured execution framework for autonomous coding agents. It enforces disciplined problem decomposition, context preservation, minimal chatter, and verifiable completion.

---

## 1. Core Principles

1. **Bias for Action over Discussion**: Do not ask unnecessary questions when reasonable defaults can be inferred. Implement, test, and demonstrate.
2. **Atomic Milestones**: Large goals must be decomposed into small, testable milestones. Never attempt a monolithic rewrite.
3. **Continuous Verification**: A task is never complete until verified with empirical evidence (test runs, build output, status codes, browser verification).
4. **Context Window Hygiene**: Keep responses concise, avoid repeating code or file dumps, and maintain a concise mental scratchpad of current state.
5. **Fail-Fast & Auto-Recovery**: When an error or failure occurs, identify the root cause immediately and pivot. Do not repeat identical failed actions.

---

## 2. GSD Phase Lifecycle

```
[Phase 1: Discovery & Planning]
          ↓
[Phase 2: Milestone Decomposition]
          ↓
[Phase 3: Incremental Execution] ←─┐
          ↓                        │ (Iterate per milestone)
[Phase 4: Empirical Verification] ─┘
          ↓
[Phase 5: Definition of Done Check]
```

### Phase 1: Discovery & Planning
- Inspect existing codebase conventions, directory structure, package managers, and configuration files.
- Locate relevant files using targeted tools (`grep_search`, `list_dir`) rather than full scans.
- Identify external dependencies, environment requirements, and constraints.

### Phase 2: Milestone Decomposition
- Formulate a clean milestone plan:
  - **Milestone 1**: Foundation / Interfaces / Schema
  - **Milestone 2**: Core Implementation / Business Logic
  - **Milestone 3**: Integration / API / UI connection
  - **Milestone 4**: Automated Tests & Validation
- Assign explicit acceptance criteria to each milestone.

### Phase 3: Incremental Execution
- Apply surgical edits using replacement tools. Never overwrite entire files if modifying only specific sections.
- Preserve existing comments, docstrings, and unrelated functionality.
- Keep changes backwards-compatible unless explicitly breaking changes were requested.

### Phase 4: Empirical Verification
- Run tests (`pytest`, `npm test`, `cargo test`, etc.) to confirm functionality.
- Inspect exit codes, logs, and error outputs directly.
- Verify both positive paths and edge cases (e.g., empty inputs, network timeouts, invalid data).

### Phase 5: Definition of Done (DoD) Checklist
Before reporting completion, confirm all of the following:
- [ ] All code compiles / passes lint and type checks without new errors.
- [ ] Automated tests pass with zero regressions.
- [ ] No temporary debug statements, leftover console logs, or scratch files left in source code.
- [ ] Modified and created files are referenced with clickable links.
- [ ] Concise summary provides clear verification results to the user.
