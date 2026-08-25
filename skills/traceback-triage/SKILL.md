---
name: traceback-triage
description: >-
  How to get a root cause out of a Python traceback, exception, or error log
  that was pasted into the conversation, when the code cannot be run: parsing
  the traceback into facts, finding the last frame in the project's own code
  rather than the deepest frame overall, following implicit and explicit
  exception chains to the link that is actually the bug, mining the exception
  message for the runtime values it encodes, mapping frames back onto the repo,
  reconstructing state that was never printed, and reporting a reading-only
  diagnosis at honest confidence. Use this whenever an error, traceback, stack
  trace, or exception message is pasted or quoted and the cause is being asked
  for — "what does this error mean", "why am I getting this", "here is the stack
  trace", "this crashed in production", "help with this error" — including when
  there is no reproduction. Pair with the debugging skill once it can be run.
meta:
  tags: [debugging, python, traceback]
---

# Diagnosing from a traceback alone

This supplements [`agents/debugger.md`](../../agents/debugger.md) and pairs with
the [`debugging`](../debugging/SKILL.md) skill. The division:

| What you have | Use |
|---|---|
| A pasted traceback, exception, or log excerpt, and no way to run the code | this skill |
| A command you can run and watch fail | the `debugging` skill |
| Both | this skill first — it is fast and it tells you where to look — then `debugging` to confirm |

A traceback is a real observation of a real run. It is weaker evidence than a
live reproduction and far stronger than reading code, and most of what it
contains is routinely skimmed. Extract everything in it before asking the caller
for anything more.

## 1. Turn the traceback into facts before forming an opinion

Write these down first. A theory formed before this step tends to survive
contact with evidence that should have killed it.

- **Exception type**, exactly, including its module if the traceback shows one.
  `ValueError` and `pydantic.ValidationError` lead to different searches.
- **The message**, verbatim, with its quoting and punctuation intact. §4.
- **The innermost frame** — the last `File ... line ... in ...` before the
  exception line. This is where the failure *surfaced*.
- **The deepest frame in this project's own code**. Usually where to look. §2.
- **The chain** — how many exceptions, joined by which connector. §3.
- **What is missing** — `[Previous line repeated N more times]`, an elided
  middle, a paste that begins mid-frame, a screenshot cropped to the last three
  lines. Truncation is itself a fact, and it changes what you can conclude.

Order convention: `Traceback (most recent call last):` means frames run
oldest-first from top to bottom, with the failure at the bottom. Read it
top-down once for the story, then bottom-up once for the mechanism.

## 2. The frame that matters is rarely the last one

Classify every frame by its path — this repo, `site-packages`, or the standard
library — and then use that classification.

**The last frame in this repo's own code is usually the one to read**, not the
deepest frame overall. Most tracebacks end several layers inside a library, and
the library is nearly always doing exactly what it was told to do. The repo
frame above it is where it was told.

Two exceptions worth knowing. A genuine bug in a dependency does happen — but
conclude it only after checking the arguments the repo passed in. And a
traceback with *no* frames from this repo at all usually means the repo's
contribution was data or configuration rather than a call: a model definition, a
settings value, a registered hook, a fixture, an entry point.

**Frames pytest changes:**

- `--tb=short` and `--tb=line` drop intermediate frames. If the middle of the
  stack is missing, that is a formatting artefact, not a short call chain — ask
  for `--tb=long -l`.
- Lines prefixed `E   ` are pytest's assertion detail, not source lines.
- `______ test_name ______` is a section header.
- Pytest rewrites assertions, so the source shown for an `assert` may not match
  the file byte-for-byte.
- A `ConftestImportFailure`, or an error during collection, happened at import
  time. Nothing in the test body ran.

**Frames that are not in the traceback at all**, which is the trap:

- Another thread's stack. `concurrent.futures` re-raises in the caller and
  chains the worker's traceback; a bare `threading.Thread` prints its exception
  and does not affect the main stack at all.
- The code that *created* an asyncio task is not in that task's traceback.
- `__del__`, weakref callbacks, and `atexit` handlers run at arbitrary points,
  so their stack says nothing about what triggered them.
- Across a process boundary, `multiprocessing` pickles the exception and the
  remote traceback often arrives embedded as *text inside the message*. Read the
  message body as a traceback in its own right.

## 3. In a chain, pick the link that is the bug

Three cases, and confusing them sends you to the wrong code:

- *"During handling of the above exception, another exception occurred"* —
  implicit chaining. The second exception was raised while the first was being
  handled. The **first** is usually the bug you were asked about; the second is
  frequently a *separate* bug in the error path — a handler referencing an
  undefined name, formatting a message with the wrong type, or assuming an
  attribute the error object does not have. Report both, and do not let the
  louder one at the bottom take all the attention.
- *"The above exception was the direct cause of the following exception"* —
  explicit `raise ... from err`. Someone deliberately wrapped the original. The
  original is the cause; the wrapper is translation.
- **No connector, and a suspiciously generic message** — `raise ... from None`
  suppressed the context, or a handler re-raised something new. The original is
  gone from what you were given. Say so; do not treat the wrapper's message as
  though it described the underlying fault.

The rule of thumb for implicit chains: the first exception happened because
something unanticipated occurred, and the second happened because the code meant
to cope with it could not. Fixing only the second one hides the first.

## 4. Mine the message for the values it encodes

This is the densest part of a traceback and the most skimmed. Python's exception
messages frequently name the **actual runtime type or value** — the one thing
you cannot obtain by reading source.

Two rules that pay for themselves immediately:

- **Values in messages are `repr`.** `KeyError: 1` and `KeyError: '1'` are
  different bugs, and the quoting is the only thing telling you which. The same
  goes for `'2024-01-01'` versus a `date`, and for a trailing space inside the
  quotes.
- **The message says what the value *was*,** which lets you work backwards.
  `'NoneType' object has no attribute 'get'` is not vague — it states that
  something returned `None`, and reduces the whole problem to *which* thing.

| Message | Hands you |
|---|---|
| `AttributeError: 'Foo' object has no attribute 'bar'` | The object's **actual runtime class**. If it is not the class you expected, the bug is upstream of this line entirely. |
| `TypeError: unsupported operand type(s) for +: 'int' and 'str'` | Both operand types, in order — left then right. |
| `ValueError: invalid literal for int() with base 10: 'abc\n'` | The offending value verbatim, including whitespace that explains it. |
| `KeyError: 'databse_url'` | The exact key that missed. Read it character by character before assuming the dict is wrong. |
| `ValueError: too many values to unpack (expected 2)` | The expected arity; the actual is in the data. |
| `TypeError: f() got an unexpected keyword argument 'x'` | The signature at runtime differs from the one you are reading — a version, a decorator, or a different function than you think. |
| `FileNotFoundError: [Errno 2] ... : 'data/x.csv'` | The exact path as resolved. Relative means the working directory is part of the bug. |

[`references/message-anatomy.md`](references/message-anatomy.md) is the full
lookup: message shape, what it hands you, and the search to run next. For what
*usually causes* a given symptom, load the `debugging` skill and use its symptom
index — this skill deliberately does not duplicate it.

## 5. Map the frames back onto the repo

For each frame in this repo, innermost first:

1. Open the file and read the **whole enclosing function**, not the cited line.
2. **Compare the source line quoted in the traceback with the line at that
   number in the file.** If they differ, stop and resolve that first — you are
   reading different code than the one that ran: another branch, a deployed
   version, an installed copy rather than the source tree. Every conclusion
   drawn after this point is worthless until it is settled.
3. Identify **which expression on that line raised**. Where several could, the
   message usually disambiguates: the type names in a `TypeError`, the attribute
   name in an `AttributeError`, the key in a `KeyError`.
4. Work backwards to where the offending value **entered the frame** — a
   parameter, a return value, an attribute, a global, an unpacking.

Then move outward until you reach a frame where the value was demonstrably fine.
The bug is between that frame and the one below it.

The caller lines quoted in the traceback are free evidence: they show the call
as written, which usually settles which of several call sites was involved
without any searching.

## 6. Reconstruct the state you were not given

You are looking for the specific value, not the category it belongs to.

Enumerate every way the value could have become what the message says it is,
then eliminate by reading. For a `None` where an object was expected:

- a function that returns on one path and falls off the end on another
- a mutating method used as if it returned a result — `sort`, `append`,
  `update`, `shuffle` all return `None`
- `.get()` or `getattr(..., None)` with a missing key
- a regex that did not match
- an attribute initialised to `None` and never set on this path
- optional config or an optional dependency that was not provided
- a mock or patch whose return value was never configured

Then check which of those actually exist in the frames you have. Usually one
survives. If two do, say so rather than picking whichever makes the better
story.

Prefer the explanation that accounts for the **exact** value in the message.
"The config was wrong" explains `KeyError: 'databse_url'` far less well than a
typo in a literal does, and the difference between those two answers is the
difference between a five-second fix and an afternoon.

If the paste includes more than the traceback — pytest `-l` locals, log lines
around it, a request id, timestamps, a repeated occurrence — use it. Locals in
particular usually collapse this whole section into one reading.

## 7. Say what the traceback cannot tell you

A reading-only diagnosis is taken on trust, so be explicit about the gaps rather
than filling them silently with whatever is convenient.

A traceback does not carry: the value of anything the message does not name;
which branch was taken in the frames above; how many iterations ran; what other
threads or tasks were doing; whether this happens every time or once in a
thousand; what the input was; or which versions were installed.

## 8. Ask for the smallest next thing

Each rung costs the caller more than the last, so ask for the cheapest one that
would settle the question:

1. **The full, untruncated traceback**, if what you have is cut, filtered,
   `--tb=short`, or a cropped screenshot.
2. **`uv run pytest -l --tb=long`** (or `python -X dev`), which adds local
   variables at every frame and frequently ends the investigation outright.
3. **Versions and environment** — `uv run pip show <pkg>`, `sys.version`, and
   whether it fails everywhere or in one place.
4. **The input, or a command that reproduces it.** Once you have this, stop
   using this skill and switch to the `debugging` skill.

Ask for one thing, give the exact command, and say what you expect it to
distinguish. A list of five requests reads as not having done the work.

## 9. Report at honest confidence

Follow the shape in the agent prompt — root cause first, then evidence citing
`file:line`, then the fix and its risks. Two obligations are specific to this
path:

- **Label it unreproduced in the first paragraph**, not the last.
- **Give the single check that would confirm it** — one command, or one value to
  print — chosen so that one outcome confirms your theory and the other kills
  it. A check that cannot fail is not a check.

Grade it honestly:

- **Confirmed by the traceback.** The message names the value and the code has
  exactly one way to produce it. This is a real level, and reaching it means you
  are done — say so plainly instead of hedging out of habit.
- **Likely.** One explanation survives; the others were eliminated by reading.
  Name what you could not rule out.
- **Candidates.** Several survive. List them in order of probability, each with
  the observation that separates it from the others. Two well-separated
  candidates with a discriminating test is a genuinely good answer; a single
  confident guess that happens to be wrong is much worse.

Never write a reading-only diagnosis in the register of a confirmed one. The
caller cannot tell which they are getting from the prose alone, and that is
exactly what they need to know in order to decide how much to trust it.
