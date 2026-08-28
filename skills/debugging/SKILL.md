---
name: debugging
description: >-
  Procedure for debugging Python: getting a failure to reproduce on demand under
  uv and pytest, reading chained tracebacks, bisecting input, history and call
  path, extracting observations from a program with nobody at an interactive
  prompt, ruling out environment faults that impersonate logic bugs, attacking
  order-, timing- and data-dependent flakiness, and diagnosing hangs, segfaults
  and vanished exceptions. Supplements the code-debugger subagent. Use this whenever
  Python code is failing and the cause is not yet known, in any phrasing — "why
  does this test fail", "fix this traceback", "this returns the wrong number",
  "it works locally but not in CI", "this test is flaky", "it hangs", "why is
  this None" — and whenever work is delegated to the code-debugger agent.
meta:
  tags: [debugging, python, testing]
---

# Debugging Python

This supplements [`agents/code-debugger.md`](../../agents/code-debugger.md). That prompt
owns the judgment — what counts as a root cause, what standard of proof applies,
when to stop. This skill owns the mechanics: the commands, the recipes, and the
catalogues. Where they overlap the agent prompt wins; it is what the caller
configured.

Read the section you need. You will not need all of it for one bug.

## 1. Get a command that fails every time

Everything downstream depends on this. A fix you cannot watch turn a red run
green is a guess with extra steps.

Projects here use **uv**. Run everything through it, so you get the project's
pinned dependencies and its interpreter:

```sh
uv sync
uv run pytest -q
```

Then narrow to the single failing case, which is the command you will repeat
several dozen times:

```sh
uv run pytest tests/test_thing.py::TestGroup::test_case -x -q
```

Never invoke bare `pytest` or `python`. Outside `uv run` you may be on a
different interpreter with different packages, and neither a red nor a green run
there tells you anything about the project.

When the failure is not in a test, write the smallest script that triggers it
into a scratch file and keep it. That script is now your test; run it after
every change.

**Make it deterministic before you start.** If the same command does not fail
the same way twice, go to §6 first — the strategies there are different from the
ones here, and mixing them wastes the most time.

| Knob | Why |
|---|---|
| `-p no:randomly` | Disable `pytest-randomly`'s order shuffling. |
| `PYTHONHASHSEED=0` | Pin string hashing, which changes set and dict-of-str iteration order between runs. |
| Seed the code's RNG explicitly | `random.seed(0)`, `np.random.seed(0)`. |
| Freeze the clock | Only with a library the repo already depends on. Do not add one. |

If `uv sync` fails, stop and report it. Do not fall back to `pip` or build a
virtualenv by hand — a different environment turns every later observation into
noise.

## 2. Read the whole traceback

The last frame printed is the innermost: where the failure *surfaced*. The frame
that put the bad value there is usually further up. Read from the top down at
least once before deciding where to look.

This section covers getting a *better* traceback out of a run you control. For
squeezing a traceback you cannot re-run — which frame to open, which link in a
chain is the bug, and the values the exception message encodes — load the
[`traceback-triage`](../traceback-triage/SKILL.md) skill.

**Chained exceptions.** The two connector lines mean different things, and
confusing them sends you to the wrong bug:

- *"During handling of the above exception, another exception occurred"* —
  implicit chaining. The second exception was raised while handling the first.
  You are looking at a failure inside an error path. The **first** exception is
  usually the bug you were sent to find; the second is often a separate bug in
  the code that was supposed to handle it. Both are worth reporting.
- *"The above exception was the direct cause of the following exception"* —
  explicit `raise ... from ...`. Someone deliberately wrapped the original. The
  original is the cause; the wrapper is just translation.

**Pytest flags that change what you can see:**

| Command | Use |
|---|---|
| `uv run pytest --tb=long -l` | Full frames **with local variables at each one**. The highest-value flag here by a distance — try it before adding a single print. |
| `uv run pytest --tb=native` | Plain CPython traceback, when pytest's own formatting is hiding the shape. |
| `uv run pytest -x` | Stop at the first failure. |
| `uv run pytest --lf` / `--ff` | Re-run last failures / run them first. |
| `uv run pytest -s` | Do not capture stdout, so your prints actually appear. |
| `uv run pytest --log-cli-level=DEBUG` | Surface the logging the codebase already has, which often beats adding prints. |
| `uv run pytest --full-trace` | Keep the entire stack including pytest internals. For debugging pytest behaviour itself, or a hang under `KeyboardInterrupt`. |
| `uv run pytest -W error` | Turn warnings into exceptions, so a silent `DeprecationWarning` or `RuntimeWarning` becomes a traceback with an origin. |

Pytest rewrites plain `assert` statements to show intermediate values. If a
failing assertion shows you nothing useful, it is probably in a helper module
pytest did not rewrite — `-l` recovers the same information.

No traceback at all, or a truncated one? Go to §7.

## 3. Narrow the search space by halving

### Halve the input

Cut the failing input in half; keep the half that still fails; repeat. Do it to
the data file, the config, the offending string, the list of records. Stop when
removing anything at all makes the failure go away.

A minimal reproducer is worth the ten minutes it takes. It usually names the
cause outright, and it becomes the regression test at the end.

### Halve the history

When the code used to work, `git bisect` finds the commit faster than reading
will:

```sh
git bisect start
git bisect bad
git bisect good <known-good-sha>
git bisect run uv run pytest tests/test_thing.py::test_case -x -q
git bisect reset
```

`git bisect run` needs a command that exits non-zero on failure; pytest does.

Bisect **checks out other commits**, so it is not a read-only operation: confirm
with the caller before starting if there is uncommitted work, and always finish
with `git bisect reset` even if the run went wrong.

When the guilty commit is large, these are faster than reading it:

```sh
git log -p -- path/to/file.py
git log -S'some_symbol' --oneline      # commits that changed the number of occurrences
git log -L :func_name:path/to/file.py  # the history of one function
```

### Halve the call path

Pick a point roughly midway between where the data is known good and where it is
known bad. Observe the value there. That tells you which half to look in next.
Three or four observations will cross a deep stack.

## 4. Getting observations out of a running program

You will usually have no one sitting at an interactive prompt, so prefer
instrumentation you can read back in captured output.

**Prints, done properly:**

```python
print(f"{value!r} type={type(value).__name__}", flush=True)
```

`!r` is not optional. `1` and `'1'` print identically without it, and that exact
distinction is the bug often enough to be worth the habit. `flush=True` matters
when the program may crash or be killed before the buffer drains. Under pytest,
add `-s` or the output disappears into the capture.

**"How did I get here?"** — for a value set by something you cannot find, or
code that runs twice:

```python
import traceback; traceback.print_stack()
```

**"What is this thing, really?"** — before theorising about an `AttributeError`:

```python
print(type(x).__mro__, sorted(vars(x)), flush=True)
```

**Non-interactive pdb**, for post-mortem inspection after an uncaught exception:

```sh
uv run python -m pdb -c continue -c "bt" -c "p sorted(locals())" -c quit script.py
```

`-c` may be repeated: `continue` runs the program, and the remaining commands
execute at the post-mortem prompt after it dies. This is fiddly and it will hang
if the program waits on input, so reach for `pytest --tb=long -l` first.

`breakpoint()` and `pytest --pdb` need a human at a terminal. Use them only when
the caller is driving the session, and never leave them behind.

**Dev mode** turns on extra runtime checks, unclosed-resource warnings, and the
fault handler in one flag:

```sh
uv run python -X dev -m pytest tests/test_thing.py -q
```

**Import diagnostics:**

```sh
uv run python -c "import mypkg; print(mypkg.__file__)"
uv run python -X importtime -c "import mypkg" 2>&1 | tail -30
```

## 5. Rule out the environment before blaming the logic

Python fails in ways that have nothing to do with the code in front of you. When
the symptom is strange — and especially when a correct-looking edit changes
nothing — rule these out early rather than late.

**You are not reading the file that is being imported.** The single most
expensive one, because every subsequent observation is about a different file
than the one you keep editing:

```sh
uv run python -c "import sys, mypkg; print(sys.executable); print(mypkg.__file__); print(sys.path[:5])"
```

Causes: the wrong virtualenv; a non-editable install shadowing the source tree;
a stale `.pyc` from a deleted `.py`; a module in the working directory with the
same name as a real one (`sys.path[0]` is the script's directory, so a local
`logging.py` or `types.py` wins); a `.pth` file adding a path you did not
expect.

**Two copies of one package, imported under different names.** Symptom:
`isinstance(x, Thing)` is false against a class that is visibly the same class,
or an `except SomeError` does not catch a `SomeError`. Confirm:

```python
print(type(x).__module__, id(type(x)), Thing.__module__, id(Thing))
```

**Version drift.** `uv run pip show <pkg>` against what the code expects, and
the interpreter version against `requires-python` in `pyproject.toml`. A
`TypeError` about an argument that clearly exists is nearly always this.

**Import-time side effects.** Module-level code that registers, connects, mutates
global config, or configures logging — including circular imports that only bite
from one entry point, so the failure follows the *caller*, not the module.

**Stale compiled artefacts.** For a package with C extensions, a `.so` built
against a different interpreter or a different version of the headers produces
errors that look nothing like their cause.

**Context differences.** Environment variables, working directory, locale,
timezone, and file permissions differ between your shell and the failing
context. `os.getcwd()` and `os.environ` in the failure path settle it.

For any `AttributeError`, `ImportError`, or `ModuleNotFoundError`, resolve the
name at runtime before forming a theory about why it is wrong:

```sh
uv run python -c "import mypkg.thing as t; print([n for n in dir(t) if 'part' in n])"
```

## 6. It only fails sometimes

Decide which of the three kinds it is first. Attacking a timing bug with the
order-dependence toolkit is the standard way to lose an afternoon.

### Order-dependent — passes alone, fails in the suite

State leaked from an earlier test. Confirm the shape:

```sh
uv run pytest tests/test_thing.py::test_case -q      # alone: does it pass?
uv run pytest -p no:randomly -q                      # fixed order: still fails?
```

Then find the culprit by halving the set of tests that run before it — run the
first half of the file, then the first quarter, and so on, or use `--deselect`
to remove suspects. With `pytest-randomly`, the seed is printed at the top of
the run; re-run with `-p randomly --randomly-seed=<n>` to reproduce that exact
order.

The leak is nearly always one of: a module-level global or cache; a class
attribute mutated through an instance; `monkeypatch`-style patching undone by
hand and missed on an error path; a fixture with `session` or `module` scope
when it needed `function`; a registry populated at import; edits to `sys.modules`
or `sys.path`; a changed logging configuration; `os.chdir` without a restore; a
singleton connection or event loop.

### Timing-dependent — threads, asyncio, subprocesses, real clocks

Reproduce by making the window **wider**, not by running it more times and
hoping: insert a sleep on one side of the suspected interleaving, shorten a
timeout, add load. Then loop it to measure the rate:

```sh
for i in $(seq 50); do uv run pytest tests/test_thing.py::test_case -q || { echo "failed on $i"; break; }; done
```

`asyncio.run(main(), debug=True)` or `PYTHONASYNCIODEBUG=1` reports slow
callbacks, un-awaited coroutines, and tasks destroyed while pending.

"It's a race" is a category, not a diagnosis. Name the two operations and the
interleaving that breaks, or keep digging.

### Data-dependent — the same code, different values

Set and dict-of-strings iteration order (`PYTHONHASHSEED`); `os.listdir` order,
which is not sorted and differs by filesystem; locale-dependent formatting,
casing, and sorting; timezone and DST boundaries; floating-point accumulation
order; anything keyed on today's date.

Run twice with `PYTHONHASHSEED=0` and then `PYTHONHASHSEED=1`. A failure that
tracks the seed is hash-order dependence, and the fix is a sort, not a retry.

## 7. Hangs, crashes, and failures with no traceback

**It hangs.** Get a stack dump of every thread rather than guessing where:

```python
import faulthandler; faulthandler.dump_traceback_later(30, exit=True)
```

```sh
PYTHONFAULTHANDLER=1 uv run python script.py
uv run pytest --timeout=30 tests/test_thing.py    # pytest-timeout, if the repo has it
```

Usual causes: a lock acquired twice or released on only one path; a subprocess
whose output pipe filled up because nobody read it (use `communicate()`, not
`wait()` after `PIPE`); a blocking call with no timeout; an `input()` reached in
a non-interactive run; a deadlock between an event loop and a synchronous call.

**It segfaults or dies without a Python error.** Nearly always a C extension or
a `ctypes` call. `PYTHONFAULTHANDLER=1` prints the Python frame it died in, which
usually identifies the library. Check the extension's build against the running
interpreter before anything else.

**It exits silently.** Look for `sys.exit()` or `os._exit()` on a path you did
not expect, an exception swallowed by a bare `except`, a `return` inside a
`finally` that discards an in-flight exception, or logging configured to a
handler that drops everything.

**The exception disappears.** Find the swallower:

```sh
grep -rn -E "except[^:]*:\s*(pass|return|continue)\s*$" --include="*.py" .
```

In asyncio, an exception in a task nobody awaited is only reported when the task
is garbage collected — sometimes long after, sometimes never. Debug mode surfaces
it. Check every `create_task` result is awaited or has a done-callback.

**`RecursionError`.** Look at the repeating unit in the traceback: a cycle of two
or three alternating frames is mutual recursion with no base case (frequently
`__getattr__` calling itself, or `__eq__` recursing through a container). A
single frame repeated is genuine depth, and the structure is the problem, not
the limit.

## 8. When the bug is "slow" or "using too much memory"

Measure before you guess; intuition about Python performance is unreliable.

```sh
uv run python -m cProfile -s cumtime script.py 2>&1 | head -40
uv run pytest --durations=10
```

Read `cumtime` to find which call tree is expensive, then `tottime` to find
where the work actually is.

For memory, compare two snapshots rather than looking at one — growth is the
signal, absolute size is not:

```python
import tracemalloc
tracemalloc.start()
before = tracemalloc.take_snapshot()
...                                       # the operation you suspect
after = tracemalloc.take_snapshot()
for stat in after.compare_to(before, "lineno")[:10]:
    print(stat)
```

Growth that never plateaus is usually an unbounded cache (including
`functools.lru_cache(maxsize=None)` on a method, which pins every `self` it ever
saw), a list appended to and never cleared, accumulating logging handlers, or a
reference cycle holding something large.

## 9. Confirm the cause before you report it

Two checks separate a cause from a plausible story. Do both.

**Falsify it.** Make the failure appear and disappear on demand: change the one
thing you claim is responsible, watch the outcome flip, then change it back and
watch it flip again. A cause you cannot switch off is a correlation.

**Explain the negative case.** Say why the code works everywhere it does work. A
mechanism that would break every call cannot explain a failure in one of them —
if you cannot account for the passing cases, you have found something true about
the code but not the reason for this bug.

Then check that the fix you are proposing addresses where the bad value was
*produced*, not the frame where it was noticed.

## 10. Clean up, then report

Remove every print, `breakpoint()`, scratch script, raised log level, added
sleep, and temporary file. Verify with the diff rather than from memory:

```sh
git status
git diff
```

If you deliberately left something in — a regression test, a log line that
genuinely helps — say so explicitly rather than letting the caller find it.

Then report in the shape the agent prompt specifies: root cause first, then the
evidence chain with `file:line`, then the fix and its risks, then your
confidence and what you could not verify.

## Reference

[`references/symptom-index.md`](references/symptom-index.md) maps a symptom to
its usual causes and the check that distinguishes them. Use it as a lookup when
you have a symptom and no lead — not as a list to read end to end.
