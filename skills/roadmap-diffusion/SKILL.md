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
- Output: a confirmed roadmap snapshot.

### Execution Phase (autonomous)

Entered after CEO says "go":

**CRITICAL: Do not stop. Do not pause. Do not ask the CEO for input.**

Once in Execution Phase, the Director runs continuously until the roadmap is done:

1. Pick the next task from the roadmap.
2. Dispatch the appropriate sub-agent(s).
3. Collect results, update documentation (roadmap file + task file).
4. Immediately move to the next task. Do NOT wait for user input between tasks.
5. Repeat until every task is either ✅ completed or ⏭️ skipped.

**When to skip (not block):**
- 🔴 Low-confidence decisions — record full context in the task file, move on.
- Sub-agent fails or returns unclear results — document what happened, move on.
- A task depends on a skipped task — skip it too, note the dependency.

**When execution is truly done:**
- All tasks processed (completed or skipped).
- Update the roadmap file with all execution results.
- Present the summary to the CEO: what got done, what was skipped, what needs decisions.
- If there are follow-up items, draft the next roadmap suggestion.

**The only reason to pause mid-execution** is if the session is about to hit context limits. In that case, write a Handoff section and tell the CEO.

## Daily Cycle

```
Morning:  review last roadmap results → feedback → approve new roadmap → "go"
Daytime:  Director executes autonomously, linear progression
Evening:  review results → feedback → Director drafts next roadmap
```

CEO intervenes ~2x/day, ~15 min each. A roadmap may span multiple days or complete within one.

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

- [ ] TNNNN task-description [confidence | change-size]
- [ ] TNNNN task-description [confidence | change-size]
- [ ] TNNNN task-description [confidence | change-size]

## Execution Results

### ✅ TNNNN task-description
- Confidence: 🟢 High
- Change size: Medium (3 files, ~150 lines)
- Result: tests pass, code in worktree `branch-name`
- Key decisions: brief summary (details in tasks/tNNNN-slug.md)

### ⏭️ TNNNN task-description — skipped, awaiting decision
- Confidence: 🔴 Low
- Change size: Large (12 files)
- Needs decision: describe the fork in the road
- Context: why this requires CEO input

### ✅ TNNNN task-description
- Confidence: 🟢 High
- Change size: Small (research only, no code changes)
- Result: recommendation summary (details in tasks/tNNNN-slug.md)

## Decisions Needed
1. 🔴 TNNNN — brief description of what needs deciding (→ tasks/tNNNN-slug.md)

## Next Steps
- Follow-up actions based on results
- Candidates for the next roadmap

## Handoff
> Written when session ends before roadmap completes.
> Captures: where we stopped, what's in progress, what's next, any open decisions.
```

### Task Template `docs/agent/tasks/tNNNN-slug.md`

One file per task. Drill into this from the roadmap for full context.

```markdown
# TNNNN Title

## Meta
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
- Worktree name (if code changes)

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
[Type]: TNNNN — clear description of what to do

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
- **High-confidence tasks**: worktree ready with passing tests, awaiting CEO push approval.
- **Low-confidence tasks**: no code changes, or draft in worktree clearly marked as pending decision.
- All changes stay linear — never auto-push, never force-push.
- Push approval happens during Planning Phase when CEO reviews results.

## Session Boundaries

This skill operates within a single Claude Code session.

- **If the session must end before the roadmap completes**: write a `## Handoff` section in the latest roadmap file capturing current state, in-progress items, and next steps.
- **Next session**: invoke the skill again. The Director reads `docs/agent/` on activation, picks up from the handoff, and enters Planning Phase with the CEO.
