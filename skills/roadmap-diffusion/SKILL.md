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
- Organize tasks into **EPICs** — numbered thematic groups (product features, tech improvements, etc.). Each EPIC gets a sequential ID (`EPIC-1`, `EPIC-2`, ...) and a short Jira-style tag (`UI`, `REN`, `SRCH`, `PERF`, etc.) so the roadmap reads as a grouped, themed plan.
- Output: a confirmed roadmap snapshot.

### Execution Phase (autonomous)

Entered after CEO says "go":

**CRITICAL: Do not stop. Do not pause. Do not ask the CEO for input.**

Once in Execution Phase, the Director runs continuously until the roadmap is done:

1. Pick the next task from the roadmap.
2. Dispatch the appropriate sub-agent(s).
3. **Verify**: dispatch a Verification sub-agent to confirm the task works (tests pass, no regressions).
4. **Commit & push**: once verified, the execution agent commits and pushes the changes immediately. Each task lands on `main` before the next task begins — no accumulated worktrees.
5. Update documentation (roadmap file + EPIC file) with results and commit hash.
6. Immediately move to the next task. Do NOT wait for user input between tasks.
7. Repeat until every task is either ✅ completed or ⏭️ skipped.

**When to skip (not block):**
- 🔴 Low-confidence decisions — record full context in the EPIC file, move on.
- Sub-agent fails or returns unclear results — document what happened, move on.
- A task depends on a skipped task — skip it too, note the dependency.

**After all roadmap tasks are processed, the Director appends the following closing tasks to the roadmap and continues the same cycle (dispatch → verify → commit & push → next):**

1. **E2E Testing & Bug Fixing** — run end-to-end tests across the full system. If bugs are found, create new tasks, fix, verify, commit & push. Iterate until clean.
2. **User Testing** — test as a target user would: realistic workflows, common use cases, edge cases. Fix critical issues found. Save findings in EPIC docs.
3. **Product Research** — synthesize feedback from testing, research competitors and market trends, think strategically about what's missing. Output: proposed product EPICs for the next roadmap.
4. **Tech Audit** — runs after product research (so it knows what features are coming). Audit the codebase for:
   - Refactoring needs, performance issues, maintainability gaps, capability gaps for proposed features.
   - Classify: **minor** findings → summary stat line (not individual tasks). **Major** findings → own EPIC and tasks in next roadmap.
5. **Draft Next Roadmap** — combine product and tech proposals into `docs/agent/roadmap/RM-{N+1}-slug.md` with status `planning`. Organize by EPIC, include rationale, prioritize by impact. Think like a product leader AND a tech leader.
6. **Executive Review Slide** — generate an HTML presentation (QBR-style) saved to `docs/agent/roadmap/RM-N-review.html`:

   **Section 1: Last Roadmap Summary**
   - **Product**: features shipped, organized by EPIC/theme. Include screenshots, demo videos/GIFs where possible. Every EPIC should have at least one visual.
   - **Stats & charts**: tasks completed, lines changed, test coverage delta, perf before/after. Use embedded charts (Chart.js, inline SVG). Numbers tell the story better than prose.
   - **Tech**: major improvements highlighted individually with before/after metrics. Minor tech changes as a brief stat line (e.g., "14 minor cleanups across 8 modules").

   **Section 2: Next Roadmap Plan**
   - **Product EPICs**: proposed features, with POC screenshots or mockups where possible.
   - **Tech EPICs**: proposed major tech work, with rationale (why now, what it unblocks).

   Style: concise, visual-heavy, executive-friendly. **Prefer visuals over text.**

**Then pause.** Present the executive review slide and proposed next roadmap to the CEO. Wait for review and sign-off before proceeding.

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

Each EPIC gets a sequential ID and a short uppercase tag (like Jira project keys):

- **Format**: `EPIC-N [TAG]` — e.g. `EPIC-1 [UI]`, `EPIC-2 [SRCH]`, `EPIC-13 [PERF]`
- **No zero-padding** — `EPIC-1`, not `EPIC-001`
- **Tags are short** (2-5 chars), derived from the theme: `UI`, `REN`, `SRCH`, `AUTH`, `PERF`, `INFRA`, `DX`, `DATA`, `API`, etc.
- **Tags are unique per roadmap** — no two EPICs share a tag within the same roadmap.
- EPIC numbers are **globally unique per project** — they never reset between roadmaps.

### In Roadmap Plans

Tasks are listed under their EPIC:

```markdown
### EPIC-1 [SRCH] — Full-text search across all content
- [ ] Add search index [🟢 | Medium]
- [ ] Search results page [🟡 | Medium]

### EPIC-2 [PERF] — Load time optimization
- [ ] Implement lazy loading [🟢 | Small]
- [ ] Add Redis caching layer [🟡 | Large]

### EPIC-3 [DX] — Code health
- [ ] Extract shared utilities [🟢 | Medium]
```

### In EPIC Files

Each EPIC doc (`docs/agent/epics/EPIC-N-slug.md`) tracks all tasks, decisions, and execution details for that EPIC.

### In Executive Review

The review slide groups results and plans by EPIC, making it easy to see what themes were addressed and what's planned.

## Document System

All documents live under `docs/agent/` in the managed project:

```
project/docs/
└── agent/
    ├── roadmap/
    │   ├── RM-1-user-profile-pages.md
    │   └── RM-2-search-module.md
    └── epics/
        ├── EPIC-1-full-text-search.md
        ├── EPIC-2-load-time-optimization.md
        └── EPIC-3-code-health.md
```

### Numbering Convention

- Roadmaps: `RM-` prefix — `RM-1`, `RM-2`, `RM-12`, `RM-103`, ...
- EPICs: `EPIC-` prefix — `EPIC-1`, `EPIC-2`, `EPIC-19`, ... (no zero-padding)
- **No zero-padding** on any ID — `RM-1`, not `RM-001`.
- All IDs are **globally unique per project** — numbers never reset between roadmaps.

### Roadmap Template `docs/agent/roadmap/RM-N-slug.md`

Each roadmap is a **planning snapshot** — the output of one planning session, not a living global document.

```markdown
# RM-N Title

## Meta
- Created: YYYY-MM-DD
- Status: planning | executing | completed | partial

## Plan
> CEO-approved direction and scope

### EPIC-N [TAG] — EPIC description
- [ ] task-description [confidence | change-size]
- [ ] task-description [confidence | change-size]

### EPIC-N [TAG] — EPIC description
- [ ] task-description [confidence | change-size]

## Execution Results

### EPIC-N [TAG]

#### ✅ task-description
- Confidence: 🟢 High
- Change size: Medium (3 files, ~150 lines)
- Result: tests pass, commit `abc1234`
- Key decisions: brief summary (details in epics/EPIC-N-slug.md)

#### ⏭️ task-description — skipped, awaiting decision
- Confidence: 🔴 Low
- Change size: Large (12 files)
- Needs decision: describe the fork in the road
- Context: why this requires CEO input

### EPIC-N [TAG]

#### ✅ task-description
- Confidence: 🟢 High
- Change size: Small (research only, no code changes)
- Result: recommendation summary (details in epics/EPIC-N-slug.md)

## Decisions Needed
1. 🔴 EPIC-N [TAG] — brief description of what needs deciding (→ epics/EPIC-N-slug.md)

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
- Link to review slide: docs/agent/roadmap/RM-N-review.html

## Next Roadmap
- Link to proposed next roadmap: docs/agent/roadmap/RM-{N+1}-slug.md
- Key themes and rationale (product + tech EPICs)

## Handoff
> Written when session ends before roadmap completes.
> Captures: where we stopped, what's in progress, what's next, any open decisions.
```

### EPIC Template `docs/agent/epics/EPIC-N-slug.md`

One file per EPIC. Drill into this from the roadmap for full context on all tasks within the EPIC.

```markdown
# EPIC-N [TAG] — Title

## Meta
- Tag: TAG
- Status: pending | in-progress | completed | partial
- Parent roadmap: RM-N

## Goal
What this EPIC achieves and why.

## Tasks

### ✅ task-description
- Confidence: 🟢 High
- Change size: Medium (3 files, ~150 lines)
- Result: tests pass, commit `abc1234`

### ⏭️ task-description — skipped
- Confidence: 🔴 Low
- Reason: why it was skipped

### 🔲 task-description — pending
- Confidence: 🟡 Medium
- Change size: Small

## Key Decisions

### Decision title
- Chose: the chosen option
- Reasoning: why this option wins
- Confidence: 🟢 High — supporting evidence
- Alternatives considered: what was rejected and why

## Execution Summary
- Files added/modified with brief descriptions
- Test results
- Commit hashes

## Screenshots
(paths to screenshots if UI changes were made)
```

## Sub-agent Dispatch

### Types

| Type | Purpose | Example prompt |
|------|---------|----------------|
| **Research** | Read code, docs, analyze current state | "Analyze the auth module architecture and summarize in docs/agent/epics/EPIC-3-auth.md" |
| **Planning** | Break down tasks, design solutions | "Design an implementation plan for EPIC-1 [SRCH], write to docs/agent/epics/EPIC-1-search.md" |
| **Execution** | Write code, run tests, produce results | "Implement and test the search API per the plan in docs/agent/epics/EPIC-1-search.md" |
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
[Type]: EPIC-N [TAG] — clear description of what to do

## Goal
What success looks like.

## Context
- Project root: /path/to/project
- Read CLAUDE.md at project root for project conventions
- Relevant files: list specific paths
- Parent roadmap: docs/agent/roadmap/RM-N-slug.md

## Constraints
- Write results to: docs/agent/epics/EPIC-N-slug.md
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
4. **On "go"**: create `docs/agent/roadmap/` and `docs/agent/epics/` directories if needed, write the roadmap and EPIC files, enter Execution Phase.

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
