---
name: code-review
description: >-
  Procedure for reviewing Python changes for correctness bugs: pinning down what
  is actually under review, gathering enough surrounding context to judge it,
  reading it in passes, and reporting each finding with a concrete failure
  scenario. Supplements the code-reviewer subagent. Use this whenever a review
  of Python code is asked for, in any phrasing — "review my changes", "review
  this PR", "look over this diff", "check this before I merge", "is this safe to
  ship", "find bugs in this file" — and whenever work is delegated to the
  code-reviewer agent. Use it even when the request sounds narrow or casual; a
  single-file glance still benefits from the evidence bar and the
  false-positive list here.
meta:
  tags: [review, quality, python]
---

# Reviewing Python for correctness

This supplements [`agents/code-reviewer.md`](../../agents/code-reviewer.md).
That prompt owns the judgment — what is in scope, what counts as a defect, what
to suspect in Python. This skill owns the procedure around it: how to establish
the target, how to build context, how to test a suspicion before it becomes a
finding, and how to write the result down.

The two are meant to be read together. Where they overlap, the agent prompt
wins; it is the thing the caller configured.

## 1. Pin the review target before reading anything

Most bad reviews come from reviewing the wrong bytes — auditing a whole file
when one function changed, or reviewing committed work when the caller meant
their uncommitted edits. Resolve this first, from what the caller said:

| The caller means | Review | Get it with |
|---|---|---|
| "my changes", "what I just did" | uncommitted work | `git diff HEAD`, plus `git status` to catch untracked files a diff will not show |
| "this branch", "before I merge", "my PR" | commits not on the base branch | `git diff main...HEAD` (three dots — diffs against the merge base, not against whatever main has moved on to) |
| "this commit" | one commit | `git show <sha>` |
| "this file", "this function" | the named code as it stands | read the file directly |

If the caller named neither a diff nor a file, `git diff HEAD` is the reasonable
default — but say in the report which target you took, so a wrong guess is
visible rather than silent.

If the diff comes back empty, stop and say so. An empty target usually means the
work is already committed or on another branch, and the caller would rather
re-point you than receive a review of nothing.

**On tooling:** the subagent's bash permission allows the read-only git commands
above and asks before anything else, which is deliberate — read files and search
the repo with the file tools rather than shelling out to `cat`, `grep`, or `gh`.
Those work without interrupting the caller. When a review genuinely needs
something else (`gh pr diff`, running the tests), asking is fine; just do it
knowingly rather than as a reflex.

## 2. Build context before judging

A diff hunk shows changed lines, not the code that has to keep working. Before
forming any opinion:

- Read the **whole** enclosing function or method, not just the changed lines.
  A three-line hunk usually cannot be judged from three lines.
- Find the **callers** of anything whose signature, return shape, exceptions, or
  defaults changed. Grep for the name. This is where the highest-severity
  findings live, and they are invisible from the diff alone.
- Look at the **tests** touching this code. A case that looks unhandled may be
  covered; a test deleted alongside a behaviour change is itself a finding.
- Note the **decorators, base classes, and validators** in play. Python resolves
  a lot at runtime, and a `@validate_call`, a Pydantic model, or an overridden
  method upstream can already handle the thing you are about to report.

Time spent here is what separates a review from a plausible-sounding guess.

## 3. Read in passes, not all at once

Trying to notice everything in one read means noticing the shallow things. Make
separate passes, in this order — it is the agent's priority order, and stopping
early still leaves the most valuable pass done:

1. **Correctness.** Follow the data. For each changed branch, ask what happens
   at the boundaries: empty input, zero, `None`, one element, the last index, a
   duplicate key, a retry. Off-by-ones and inverted conditions surface here.
2. **Contracts.** What did callers rely on before that is no longer true? Return
   type or shape, raised exceptions, mutation of arguments, default values,
   ordering guarantees, whether `None` was previously possible.
3. **Security and resources.** Only where the change touches a trust boundary or
   acquires something: untrusted input reaching a shell, a query, a
   deserializer, or a filesystem path; files, sockets, subprocesses, locks, and
   sessions opened without guaranteed release.
4. **Reuse and simplification.** Something the repo already does elsewhere, or
   machinery out of proportion to the problem. Report these last and briefly.

See [`references/python-pitfalls.md`](references/python-pitfalls.md) for the
expanded checklist — each entry has what it looks like, how to confirm it, and
when the same shape is not a bug. Consult it when something looks off and you
want to check the shape, not as a list to walk end to end.

## 4. Clear the evidence bar

A finding is a claim that this code will misbehave. Before writing one down,
construct the failure concretely:

- Name the **input or state** that triggers it — an actual value, not "invalid
  input".
- Trace the **path** through the code that reaches the defect, checking as you
  go that nothing earlier short-circuits it.
- State the **wrong result** — the exception, the incorrect value, the leaked
  handle, the corrupted row.

If you cannot fill in all three, you have a suspicion. Either dig until it is a
finding or drop it. Reporting suspicions as findings is expensive in a way that
is easy to underrate: the caller spends real time disproving each one, and after
a couple of false alarms they stop reading the rest of the review — including
the finding that was correct.

### Shapes that look like bugs and usually are not

Check these before reporting, because they are the most common false alarms:

- A **mutable default argument** that is only ever read, never mutated. Still
  worth a one-line note, not a correctness finding.
- **`except Exception:` that logs and re-raises**, or that is the deliberate
  boundary of a task runner, request handler, or plugin loader. Swallowing is
  the defect; catching broadly is not.
- **`if not x:`** where `x` is a `bool`, or where the empty case and the `None`
  case genuinely want the same handling.
- **A missing `with`** on an object that a fixture, dependency injector, or
  caller-owned context manager closes. Follow the ownership before reporting.
- **A bare `assert`** in tests, or in code that is not run under `-O`.
- **Pre-existing issues the diff did not touch.** Out of scope. Mention at most
  in a closing line if severe, and label it as pre-existing.

## 5. Report

Order findings most severe first — severity meaning what it costs if it ships,
not how interesting it was to find. For each:

```
### <file>:<line> — <one sentence naming the defect>

<How it fails: the input or state, the path, the wrong result.>

Confidence: <confirmed | likely — what you could not verify>
```

Then, if anything applies, a short **Minor** section for the reuse and
simplification notes, one line each.

Do not propose patches unless asked; this agent reports and does not edit.
Pointing at the fix in a clause ("the guard belongs before the `open`") is
useful, a rewritten function is not.

If the review is clean, say that plainly and say what you covered — "reviewed
the 3 changed functions in `parser.py` against their callers; no correctness
issues found". A clean review stated with its scope is a useful result. Padding
it with speculative nitpicks to look thorough is the failure mode to avoid.
