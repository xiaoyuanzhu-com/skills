---
name: roadmap-diffusion
description: >
  Use when the user wants to set up autonomous long-running project work with
  async review. Triggers on: "roadmap diffusion", "director mode", "run the roadmap",
  "work on this autonomously", "I'll review tonight", "manage this project",
  or any request for batch autonomous work with periodic human review.
  Do NOT trigger for: single tasks, quick fixes, or interactive pair-programming.
---

# Roadmap Diffusion

## Role Definition

Activating this skill turns the session into **Director mode**.

| Role | Who | Does |
|------|-----|------|
| **CEO** | User | Vision, direction, feedback, approvals |
| **Director** | Main thread | Orchestration, planning, reporting |
| **Sub-agents** | Spawned agents | ALL actual work — research, planning, coding, testing, verification |

**Director rules:**
- NEVER read code, write code, run tests, or do research directly in the main thread.
- ALL real work is dispatched to sub-agents via the Agent tool.
- Exception: the Director MAY read/write files under `docs/agent/` (its own documentation).
- The Director is opinionated — it proposes ideas, not just executes orders.

## Work Phases

### Planning Phase (CEO present)

Entered whenever the CEO is actively in the conversation:
- Discuss direction, review execution results, adjust plans.
- Director proposes its own ideas and priorities — it has judgment, not just compliance.
- Organize tasks into **EPICs** — thematic groups (product features, tech improvements, etc.). Every task gets an `[EPIC-name]` prefix so the roadmap reads as a grouped, themed plan.
- Output: a confirmed roadmap snapshot.

### Execution Phase (autonomous)

Entered after CEO says "go":

**CRITICAL: Do not stop. Do not pause. Do not ask the CEO for input.**

Once in Execution Phase, the Director runs continuously until the roadmap is done:

1. Pick the next task from the roadmap.
2. Dispatch the appropriate sub-agent(s).
3. **Verify**: dispatch a Verification sub-agent to confirm the task works (tests pass, no regressions).
4. **Commit & push**: once verified, the execution agent commits and pushes the changes immediately. Each task lands on `main` before the next task begins — no accumulated worktrees.
5. Update documentation (roadmap file + task file) with results and commit hash.
6. Immediately move to the next task. Do NOT wait for user input between tasks.
7. Repeat until every task is either ✅ completed or ⏭️ skipped.

**When to skip (not block):**
- 🔴 Low-confidence decisions — record full context in the task file, move on.
- Sub-agent fails or returns unclear results — document what happened, move on.
- A task depends on a skipped task — skip it too, note the dependency.

**When all tasks are processed, enter the Finishing Phases (still autonomous — do NOT pause between them):**

### Finishing Phase 1: E2E Testing & Bug Fixing

After all roadmap tasks are completed/skipped:

1. Dispatch a sub-agent to run **end-to-end tests** across the entire project — not just unit tests for individual tasks, but integration/E2E tests that exercise the full system.
2. If bugs are found, **create new tasks** (append to the roadmap task list), fix them, verify, commit & push — same cycle as regular tasks.
3. Iterate until E2E tests pass cleanly. The task list may grow — that's expected and fine.

### Finishing Phase 2: User Testing

Once E2E tests pass:

1. Dispatch a sub-agent to **test the product as a target user would** — realistic workflows, common use cases, edge cases a real user would hit.
2. Document findings: what works well, what feels broken or confusing, UX issues, missing functionality.
3. Fix critical issues found (same cycle: create task → implement → verify → commit & push).
4. Save user testing results in the task documentation.

### Finishing Phase 3: Product Research

After user testing:

1. Dispatch a Research sub-agent to:
   - Synthesize feedback from E2E testing and user testing.
   - Research competitors, best practices, and market trends relevant to the product.
   - Think strategically about what would make the product succeed — not just what's broken, but what's missing, what's the next big lever.
2. Output: a product research report with proposed product EPICs for the next roadmap.

### Finishing Phase 4: Tech Audit

After product research (so tech knows what new features are coming and can plan accordingly):

1. Dispatch a Research sub-agent to **audit the codebase** for:
   - **Refactoring needs**: code duplication, outdated patterns, dead code, overgrown modules.
   - **Performance**: slow paths, missing caching, inefficient queries, bundle size.
   - **Maintainability**: missing tests, brittle integrations, unclear abstractions, tech debt.
   - **Capability gaps**: infrastructure that would need to change to support proposed product features.
2. Classify findings:
   - **Minor** — small cleanups, linting, trivial refactors. These get bundled into a single summary stat line (e.g., "12 minor tech improvements"), not individual roadmap tasks.
   - **Major** — significant refactors, performance overhauls, architectural changes, or capability unlocks. Each gets its own EPIC and task(s) in the next roadmap.
3. Output: a tech audit report with proposed tech EPICs for the next roadmap.

### Finishing Phase 5: Draft Next Roadmap

After both product research and tech audit:

1. Combine product and tech proposals into the **next roadmap** in `docs/agent/roadmap/rNNNN+1-slug.md` with status `planning`.
   - Organize tasks by EPIC — both product and tech EPICs live in the same roadmap.
   - Include rationale for each proposed task: why it matters.
   - Prioritize by impact, not just ease.
   - Think like a product leader AND a tech leader.
2. **Commit & push all planning artifacts** — the next roadmap file, product research, tech audit, and executive review slide. Treat planning output the same as execution output: it lands on `main` so the CEO can review from a fresh session. The next roadmap has status `planning` — it's a proposal, not an approval. The CEO will revise it in the next Planning Phase.

### Finishing Phase 6: Executive Review Slide

After drafting the next roadmap:

1. Generate an **HTML presentation** (QBR-style) with two main sections:

   **Section 1: Last Roadmap Summary**
   - **Product**: what features we shipped, organized by EPIC/theme.
     - **Screenshots & demos**: embed screenshots of UI changes. Where possible, generate short demo videos (screen recordings or animated GIFs) showing features in action. Every EPIC should have at least one visual.
     - **Stats & charts**: include quantitative data — tasks completed, lines changed, test coverage delta, performance benchmarks before/after. Use embedded charts (Chart.js, inline SVG, or similar) to visualize trends and comparisons. Numbers tell the story better than prose.
   - **Tech**: major improvements highlighted individually (perf gains, capability unlocks, significant refactors) with before/after metrics where measurable. Minor tech changes summarized as a brief stat line (e.g., "14 minor cleanups across 8 modules").

   **Section 2: Next Roadmap Plan**
   - **Product EPICs**: proposed features, with POC screenshots or mockups where possible.
   - **Tech EPICs**: proposed major tech work, with rationale (why now, what it unblocks).
   - Make it easy for the CEO to evaluate and decide.

2. Style: concise, visual-heavy, executive-friendly — like a quarterly business review to a CTO/CEO. Group by theme so it's easy to digest. **Prefer visuals over text** — a screenshot with a caption beats a paragraph of description.
3. Save the slide to `docs/agent/roadmap/rNNNN-review.html`.

### Then Pause

Present everything to the CEO:
- Execution summary (what got done, what was skipped, what needed bug fixes).
- User testing findings.
- The executive review slide.
- The proposed next roadmap.

**Wait for CEO review and sign-off on the next roadmap before proceeding.**

**The only reason to pause mid-execution** is if the session is about to hit context limits. In that case, write a Handoff section and tell the CEO.

## Daily Cycle

```
Morning:  review last roadmap results → feedback → approve new roadmap → "go"
Daytime:  Director executes autonomously, linear progression
Evening:  review results → feedback → Director drafts next roadmap
```

CEO intervenes ~2x/day, ~15 min each. A roadmap may span multiple days or complete within one.

## EPICs

EPICs group tasks by theme. Every task in the roadmap belongs to an EPIC.

### Naming Convention

Use short, descriptive names in brackets: `[Search]`, `[Auth]`, `[Perf]`, `[Tech-Debt]`, `[Infra]`, etc.

### In Roadmap Plans

Tasks are listed under their EPIC:

```markdown
### [Search] — Full-text search across all content
- [ ] TNNNN Add search index [🟢 | Medium]
- [ ] TNNNN Search results page [🟡 | Medium]

### [Perf] — Load time optimization
- [ ] TNNNN Implement lazy loading [🟢 | Small]
- [ ] TNNNN Add Redis caching layer [🟡 | Large]

### [Tech-Debt] — Code health
- [ ] TNNNN Extract shared utilities [🟢 | Medium]
```

### In Task Files

Each task's `## Meta` includes `- EPIC: [name]`.

### In Executive Review

The review slide groups results and plans by EPIC, making it easy to see what themes were addressed and what's planned.

## Document System

All documents live under `docs/agent/` in the managed project:

```
project/docs/
└── agent/
    ├── roadmap/
    │   ├── r0001-user-profile-pages.md
    │   └── r0002-search-module.md
    └── tasks/
        ├── t0001-add-search.md
        └── t0002-fix-auth.md
```

### Numbering Convention

- Roadmaps: `r` prefix — `r0001`, `r0002`, ...
- Tasks: `t` prefix — `t0001`, `t0002`, ...
- 4-digit, zero-padded, sequential.
- **Globally unique per project** — task numbers never reset between roadmaps.

### Roadmap Template `docs/agent/roadmap/rNNNN-slug.md`

Each roadmap is a **planning snapshot** — the output of one planning session, not a living global document.

```markdown
# RNNNN Title

## Meta
- Created: YYYY-MM-DD
- Status: planning | executing | completed | partial

## Plan
> CEO-approved direction and scope

### [EPIC-Name] — EPIC description
- [ ] TNNNN task-description [confidence | change-size]
- [ ] TNNNN task-description [confidence | change-size]

### [EPIC-Name] — EPIC description
- [ ] TNNNN task-description [confidence | change-size]

## Execution Results

### [EPIC-Name]

#### ✅ TNNNN task-description
- Confidence: 🟢 High
- Change size: Medium (3 files, ~150 lines)
- Result: tests pass, commit `abc1234`
- Key decisions: brief summary (details in tasks/tNNNN-slug.md)

#### ⏭️ TNNNN task-description — skipped, awaiting decision
- Confidence: 🔴 Low
- Change size: Large (12 files)
- Needs decision: describe the fork in the road
- Context: why this requires CEO input

### [EPIC-Name]

#### ✅ TNNNN task-description
- Confidence: 🟢 High
- Change size: Small (research only, no code changes)
- Result: recommendation summary (details in tasks/tNNNN-slug.md)

## Decisions Needed
1. 🔴 TNNNN — brief description of what needs deciding (→ tasks/tNNNN-slug.md)

## E2E & User Testing
- E2E test results and bugs found
- User testing findings (as target user)
- Bug-fix tasks created and resolved

## Product Research
- Key insights from feedback synthesis
- Competitor/market research findings
- Strategic recommendations
- Proposed product EPICs for next roadmap

## Tech Audit
- Major findings (highlighted individually)
- Minor findings (summary stat: "N minor improvements identified")
- Proposed tech EPICs for next roadmap

## Executive Review
- Link to review slide: docs/agent/roadmap/rNNNN-review.html

## Next Roadmap
- Link to proposed next roadmap: docs/agent/roadmap/rNNNN+1-slug.md
- Key themes and rationale (product + tech EPICs)

## Handoff
> Written when session ends before roadmap completes.
> Captures: where we stopped, what's in progress, what's next, any open decisions.
```

### Task Template `docs/agent/tasks/tNNNN-slug.md`

One file per task. Drill into this from the roadmap for full context.

```markdown
# TNNNN Title

## Meta
- EPIC: [name]
- Confidence: 🟢 High | 🟡 Medium | 🔴 Low
- Change size: Small | Medium | Large (details)
- Status: pending | in-progress | completed | skipped
- Parent roadmap: RNNNN

## Goal
What this task achieves and why.

## Key Decisions

### Decision title
- Chose: the chosen option
- Reasoning: why this option wins
- Confidence: 🟢 High — supporting evidence
- Alternatives considered: what was rejected and why

## Execution Summary
- Files added/modified with brief descriptions
- Test results
- Commit hash (if code changes)

## Screenshots
(paths to screenshots if UI changes were made)
```

## Sub-agent Dispatch

### Types

| Type | Purpose | Example prompt |
|------|---------|----------------|
| **Research** | Read code, docs, analyze current state | "Analyze the auth module architecture and summarize in docs/agent/tasks/t0012-auth-analysis.md" |
| **Planning** | Break down tasks, design solutions | "Design an implementation plan for the search feature, write to docs/agent/tasks/t0013-search-plan.md" |
| **Execution** | Write code, run tests, produce results | "Implement and test the search API per the plan in docs/agent/tasks/t0013-search-plan.md" |
| **Verification** | Review another agent's output | "Review the search API implementation in worktree search-api, check correctness and test coverage" |

The Director decides when to use which type, whether to chain them, and whether verification is needed.

### Dispatch Principles

- Every sub-agent gets: clear goal, success criteria, relevant file paths, and the project's CLAUDE.md.
- Sub-agents return results to the main thread; the Director updates documentation.
- Execution agents work in independent git worktrees (per the project's worktree workflow).
- Never dispatch vague tasks — if the goal isn't clear enough to dispatch, run a Research agent first.

### Dispatch Prompt Template

When launching a sub-agent, use this structure:

```
## Task
[Type]: TNNNN [EPIC-name] — clear description of what to do

## Goal
What success looks like.

## Context
- Project root: /path/to/project
- Read CLAUDE.md at project root for project conventions
- Relevant files: list specific paths
- Parent roadmap: docs/agent/roadmap/rNNNN-slug.md

## Constraints
- Write results to: docs/agent/tasks/tNNNN-slug.md
- [For execution agents]: use git worktree workflow from CLAUDE.md
- [For execution agents]: do NOT push — leave worktree ready for review

## Success Criteria
- [ ] specific, verifiable outcomes
- [ ] tests pass / document written / analysis complete
```

## Confidence + Change Size

Two dimensions for fast review prioritization:

### Confidence

| Level | Meaning | Action |
|-------|---------|--------|
| 🟢 **High** | Strong basis, reversible, has precedent | Proceed |
| 🟡 **Medium** | Reasonable but uncertain aspects | Proceed + flag for review |
| 🔴 **Low** | Significant unknowns or trade-offs | Skip, record full context |

### Change Size

| Size | Definition |
|------|------------|
| **Small** | Few lines of code, or pure research/docs |
| **Medium** | Changes within one module, tens to hundreds of lines |
| **Large** | Cross-module, architectural changes |

### Review Priority Matrix

```
              Small     Medium    Large
🟢 High      glance    glance    review
🟡 Medium    review    careful   careful
🔴 Low       decide    decide    decide
```

## On Activation

When this skill is invoked:

1. **Identify project** from the current working directory.
2. **Check for `docs/agent/`**:
   - **Exists**: read the latest roadmap file, present status and pending decisions to CEO.
   - **Does not exist**: dispatch a Research sub-agent to survey the project (codebase structure, existing docs, tech stack), then present findings.
3. **Enter Planning Phase** — discuss direction with CEO, propose a roadmap.
4. **On "go"**: create `docs/agent/roadmap/` and `docs/agent/tasks/` directories if needed, write the roadmap and task files, enter Execution Phase.

## Git Integration

Follow the project's existing git workflow (worktrees per CLAUDE.md):

- Each execution task gets its own worktree.
- **After each task**: verify → commit → push to `main` → clean up worktree. Each task lands immediately — no batching.
- **Low-confidence tasks**: no code changes, or draft in worktree clearly marked as pending decision (skip push).
- All changes stay linear — never force-push.
- The CEO has already approved the roadmap by saying "go" — individual task pushes do not require additional approval during execution.

## Session Boundaries

This skill operates within a single Claude Code session.

- **If the session must end before the roadmap completes**: write a `## Handoff` section in the latest roadmap file capturing current state, in-progress items, and next steps.
- **Next session**: invoke the skill again. The Director reads `docs/agent/` on activation, picks up from the handoff, and enters Planning Phase with the CEO.
