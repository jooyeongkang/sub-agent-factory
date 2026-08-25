# Symptom index: what it usually is, and how to tell

A lookup for when you have a symptom and no lead. Each entry has three parts:

- **Looks like** — the message or behaviour, as it appears.
- **Usual causes** — ordered roughly by how often they turn out to be it.
- **Tell them apart by** — the observation that picks one, rather than a list to
  reason about.

Do not read this top to bottom. Jump to the symptom, take the check, and get
back to the bug. A cause found here is still a hypothesis until you have watched
it produce the failure — see §9 of the skill.

## Contents

- [`AttributeError: 'NoneType' object has no attribute ...`](#attributeerror-nonetype-object-has-no-attribute-)
- [`AttributeError: module 'x' has no attribute 'y'`](#attributeerror-module-x-has-no-attribute-y)
- [`ImportError` / `ModuleNotFoundError`](#importerror--modulenotfounderror)
- [`ImportError: cannot import name ... (most likely due to a circular import)`](#importerror-cannot-import-name--most-likely-due-to-a-circular-import)
- [My edit has no effect](#my-edit-has-no-effect)
- [`isinstance` is false for the right class](#isinstance-is-false-for-the-right-class)
- [Wrong value, no exception](#wrong-value-no-exception)
- [A value changed and nothing assigned to it](#a-value-changed-and-nothing-assigned-to-it)
- [The second call behaves differently from the first](#the-second-call-behaves-differently-from-the-first)
- [`KeyError` / `IndexError` on data that is obviously there](#keyerror--indexerror-on-data-that-is-obviously-there)
- [`TypeError` about an argument that clearly exists](#typeerror-about-an-argument-that-clearly-exists)
- [Passes alone, fails in the suite](#passes-alone-fails-in-the-suite)
- [Passes locally, fails in CI](#passes-locally-fails-in-ci)
- [Every callback does the same thing](#every-callback-does-the-same-thing)
- [The iterable is empty the second time](#the-iterable-is-empty-the-second-time)
- [`RuntimeError: dictionary changed size during iteration`](#runtimeerror-dictionary-changed-size-during-iteration)
- [Nothing happens and there is no error](#nothing-happens-and-there-is-no-error)
- [`RuntimeWarning: coroutine ... was never awaited`](#runtimewarning-coroutine--was-never-awaited)
- [Async code hangs or an event loop complains](#async-code-hangs-or-an-event-loop-complains)
- [It hangs](#it-hangs)
- [Segfault or a crash with no traceback](#segfault-or-a-crash-with-no-traceback)
- [`RecursionError`](#recursionerror)
- [`UnicodeDecodeError` / mojibake](#unicodedecodeerror--mojibake)
- [The file is empty or truncated](#the-file-is-empty-or-truncated)
- [Datetime is off by hours, or compares wrongly](#datetime-is-off-by-hours-or-compares-wrongly)
- [Floating-point comparison fails by a hair](#floating-point-comparison-fails-by-a-hair)
- [Memory grows and never comes back](#memory-grows-and-never-comes-back)
- [The mock was not called](#the-mock-was-not-called)

## `AttributeError: 'NoneType' object has no attribute ...`

**Looks like** an attribute access on a `None` that should have been an object.

**Usual causes**

- A function that returns a value on one path and falls off the end on another,
  returning `None` implicitly. Missing `return` in a branch, or `return` inside a
  loop that did not execute.
- A method that mutates in place and returns `None` used as if it returned the
  result: `xs = xs.sort()`, `xs = xs.append(y)`, `s = s.replace(...)` — the last
  one does return, but `list.sort`, `list.append`, `dict.update`, and
  `random.shuffle` do not.
- `re.match` / `re.search` that did not match.
- `dict.get(k)` where the key is absent and no default was given.
- An ORM or API lookup that legitimately found nothing.

**Tell them apart by** finding where the `None` was produced, not where it was
used. Print the value at the assignment, or run `pytest -l --tb=long` and read
the locals in the frame *above* the crash. The frame that raised is nearly never
the one to fix.

## `AttributeError: module 'x' has no attribute 'y'`

**Usual causes**

- A local file shadowing a real module — a `queue.py`, `types.py`, `select.py`,
  or `email.py` in the working directory.
- A partially initialised module, mid-circular-import.
- A version where the attribute has moved or been removed.
- A stray `x.pyc` or a stale package directory.

**Tell them apart by** `python -c "import x; print(x.__file__)"`. If the path is
not the one you expect, that is the whole bug.

## `ImportError` / `ModuleNotFoundError`

**Usual causes**

- The wrong interpreter, i.e. not running under `uv run`.
- The package is installed but not in this environment, or installed under a
  different distribution name than the import name.
- A namespace-package layout with a missing `__init__.py`, or a `src/` layout
  that was never installed.
- The script's own directory is `sys.path[0]`, so `python subdir/script.py` sees
  a different path than `python -m pkg.script`.

**Tell them apart by** printing `sys.executable` and `sys.path` from inside the
failing context, then `uv run pip show <dist-name>`.

## `ImportError: cannot import name ... (most likely due to a circular import)`

**Usual causes** two modules importing each other at module level, where which
one fails depends entirely on which was imported first — so the error follows the
entry point rather than the code.

**Tell them apart by** reading the traceback's import chain from the top: it
lists the cycle in order. The fix is normally to move one import inside the
function that uses it, or to move the shared thing to a third module. Note that
`from x import thing` fails where `import x` would have succeeded, because it
resolves the name immediately.

## My edit has no effect

**Usual causes**

- You are editing a different file than the one being imported (installed copy
  vs source tree, wrong virtualenv, duplicated tree).
- A stale `.pyc` where the `.py` was deleted or renamed.
- A long-running process, worker, or notebook kernel that has not re-imported.
- The code path is not reached at all — a cached result, an early return, a
  feature flag, an overridden method.

**Tell them apart by** adding a deliberate syntax error to the file and re-running.
If the run still succeeds, the file is not being executed and nothing else you
observe about it means anything.

## `isinstance` is false for the right class

**Usual causes**

- The module was imported twice under two names, so there are two distinct class
  objects (`pkg.mod` and `mod`, or a reloaded module).
- `importlib.reload` left old instances behind pointing at the old class.
- A mock, proxy, or dynamically generated subclass.

**Tell them apart by** comparing `type(x).__module__` and `id(type(x))` against
`Cls.__module__` and `id(Cls)`.

## Wrong value, no exception

**Usual causes**

- An inverted or off-by-one boundary — `<` for `<=`, a range end, a slice bound.
- Integer division, or truncation where rounding was meant.
- Operator precedence, especially `and`/`or` mixed with comparisons, and
  `not x == y`.
- A chained comparison or a `%` on a negative number behaving as specified but
  not as assumed.
- Shadowing: a local name reusing an outer one, so the write goes somewhere the
  read never sees.

**Tell them apart by** halving the call path (§3 of the skill): print the value
midway between known-good and known-bad and repeat. Guessing which line is wrong
from reading is exactly the step this replaces.

## A value changed and nothing assigned to it

**Usual causes**

- Aliasing: two names bound to the same list or dict, so mutation through one is
  visible through the other. `b = a` does not copy; `dict(a)` and `a[:]` are
  shallow, so nested values are still shared.
- A mutable default argument (`def f(xs=[])`) accumulating across calls.
- A class attribute mutated through an instance, shared by every instance.
- A dataclass field with a mutable default shared via `default` rather than
  `default_factory`.
- Something downstream mutating a collection you passed in.

**Tell them apart by** printing `id(obj)` at both places. Same id means one
object, and the question becomes who else holds a reference —
`traceback.print_stack()` at the mutation answers that.

## The second call behaves differently from the first

**Usual causes** a cache (`functools.lru_cache`, `cached_property`, a module-level
dict), a generator or file handle already consumed, a lazily-initialised global,
a connection pool, or accumulated state in a mutable default.

**Tell them apart by** running the operation twice in one process and printing the
result of each. If only the second is wrong, the state that differs between them
is the bug.

## `KeyError` / `IndexError` on data that is obviously there

**Usual causes**

- A type mismatch in the key: `1` vs `"1"`, `Decimal` vs `float`, a `Path` vs a
  `str`, or an enum vs its value.
- Whitespace or a BOM on a key read from a file — a leading `﻿` on the first
  CSV header is the classic.
- Case difference, or an unnormalised Unicode form that looks identical.
- A dict rebuilt or filtered earlier than you think.

**Tell them apart by** printing `repr` of both the key and the available keys,
plus their types:

```python
print(repr(key), type(key), [(repr(k), type(k)) for k in d][:10])
```

## `TypeError` about an argument that clearly exists

**Usual causes**

- A version mismatch: the installed package is older or newer than the code
  expects.
- A decorator that changed the signature, or a `functools.partial`.
- Calling an unbound method, or forgetting `self`/`cls` in a definition.
- A keyword-only parameter passed positionally, or the reverse.

**Tell them apart by** `uv run python -c "import inspect, mod; print(inspect.signature(mod.thing))"`
— the actual signature at runtime, not the one in the docs or in the source you
happen to be reading.

## Passes alone, fails in the suite

**Usual causes** state that leaked from an earlier test. See §6 of the skill for
the halving procedure and the full list of leak sites.

**Tell them apart by** running it alone, then with `-p no:randomly`, then
bisecting the set of tests that run before it.

## Passes locally, fails in CI

**Usual causes** in rough order: a different Python or dependency version; a
missing or different environment variable; a different working directory; test
order or parallelism (`-n auto`); timezone or locale; a case-insensitive local
filesystem versus a case-sensitive one in CI; a file present locally but not
committed; a slower machine exposing a timing assumption; no network.

**Tell them apart by** printing the environment from inside the CI run —
`sys.version`, `os.getcwd()`, `sorted(os.environ)`, `time.tzname`, and the output
of `uv run pip list` — and diffing it against the same locally. Almost every
instance of this is visible in that diff.

## Every callback does the same thing

**Looks like** a list of lambdas or partials that all use the final loop value.

**Usual causes** a closure captures the *variable*, not its value at creation:

```python
fns = [lambda: print(i) for i in range(3)]   # all print 2
```

**Tell them apart by** checking whether the closure is called after the loop
ends. If so, that is it; bind with a default argument (`lambda i=i: ...`) or
`functools.partial`.

## The iterable is empty the second time

**Usual causes** a generator, `map`, `filter`, `zip`, `csv.reader`, or a file
object that was already consumed. Also a `Cursor` or a streamed response body.

**Tell them apart by** checking whether anything earlier iterated it — including
a `len()`-free truthiness check, a `sum()`, or a log line. If it must be
traversed twice, materialise it into a list once and use that.

## `RuntimeError: dictionary changed size during iteration`

**Usual causes** a mutation inside a loop over the same collection, sometimes
indirectly through a called function or a `__del__`. The same applies to sets and
to `RuntimeError: Set changed size during iteration`.

**Tell them apart by** iterating over a snapshot (`list(d)`, `list(d.items())`)
and seeing whether the error moves elsewhere — if the underlying logic is
correct, the snapshot is also the fix.

## Nothing happens and there is no error

**Usual causes**

- A generator function never iterated — the body of a function containing
  `yield` does not run until you consume it.
- A condition that is never true; add an `else` that raises to prove the branch.
- An exception swallowed by a bare `except`.
- Output going to a logger with no handler, or captured by pytest (add `-s`).
- `sys.exit()` on an unexpected path.
- Work submitted to an executor or task whose result is never awaited.

**Tell them apart by** putting a print as the first statement of the function
you believe runs. Establish that it runs at all before investigating what it
does.

## `RuntimeWarning: coroutine ... was never awaited`

**Usual causes** an `async def` called without `await`; a coroutine passed where
a callable was expected; `asyncio.gather` on results that were already awaited;
mocking an async function with a plain `Mock` instead of `AsyncMock`.

**Tell them apart by** running with `-W error::RuntimeWarning` so the warning
becomes an exception with a traceback pointing at the call site.

## Async code hangs or an event loop complains

**Usual causes**

- A blocking synchronous call inside a coroutine (a `requests` call, `time.sleep`,
  a synchronous DB driver, heavy CPU work) starving the loop.
- `asyncio.run` called while a loop is already running, or two loops in one
  process.
- A task created and never awaited, so its exception disappears.
- An `await` on something holding a lock that the awaited thing needs.

**Tell them apart by** `PYTHONASYNCIODEBUG=1`, which reports slow callbacks with
the frame that blocked, plus tasks destroyed while pending.

## It hangs

**Usual causes** deadlock on a lock taken twice or released on only one path; a
subprocess pipe filled because nothing is reading it; a blocking call with no
timeout; `input()` in a non-interactive context; an infinite loop whose exit
condition can never be reached.

**Tell them apart by** dumping every thread's stack rather than guessing:

```python
import faulthandler; faulthandler.dump_traceback_later(30, exit=True)
```

The frame at the bottom of each thread's dump is where it is stuck. For
subprocesses, `communicate()` rather than `wait()` after using `PIPE`.

## Segfault or a crash with no traceback

**Usual causes** a C extension mismatched to the interpreter or to another
library's ABI (NumPy-linked packages are the usual suspects); a `ctypes` call
with wrong argument types; running out of stack in a native call; occasionally
an OOM kill, which is not a crash in the program at all.

**Tell them apart by** `PYTHONFAULTHANDLER=1`, which prints the Python frame at
the point of death and so names the library. Check the OS log or exit code for
signal 9 before assuming a segfault: killed and crashed look similar from
inside.

## `RecursionError`

**Usual causes** a missing base case; `__getattr__` that touches `self.x` for an
attribute that does not exist and so calls itself; `__eq__` or `__repr__`
recursing through a cyclic structure; a data structure with a cycle in it.

**Tell them apart by** looking at the repeating unit in the traceback. Two or
three alternating frames is mutual recursion with no terminator; one frame
repeated is genuine depth. Raising `sys.setrecursionlimit` is a diagnosis only
in the second case, and rarely the fix.

## `UnicodeDecodeError` / mojibake

**Usual causes** `open()` without an explicit `encoding`, which uses the
platform default — UTF-8 on Linux and macOS, historically cp1252 on Windows;
bytes decoded twice; a file that is genuinely in another encoding; a BOM.

**Tell them apart by** looking at the raw bytes around the reported position:

```python
data = open(path, "rb").read()
print(data[max(0, pos-20):pos+20])
```

Always pass `encoding="utf-8"` explicitly rather than relying on the default.
`errors="replace"` is for inspection, not for the fix.

## The file is empty or truncated

**Usual causes** never closed, so the buffer was not flushed — `open()` without
a `with`, or a process that exited via `os._exit()`; two writers to one path;
opening with `"w"` in a retry loop and truncating a good file; reading before a
subprocess finished writing.

**Tell them apart by** checking whether the writer used a context manager, and
whether the size is zero (never flushed) or a round number like 4096 or 8192
(one buffer written, the rest lost).

## Datetime is off by hours, or compares wrongly

**Usual causes** naive and aware datetimes mixed; `datetime.utcnow()`, which
returns a *naive* datetime that is not local time and is a trap by construction;
storing local time and reading it as UTC; a DST boundary; `date` compared against
`datetime`.

**Tell them apart by** printing `dt.tzinfo` for every value involved. Any `None`
in that set is the bug. Prefer `datetime.now(timezone.utc)` over `utcnow()`.

## Floating-point comparison fails by a hair

**Usual causes** exact `==` on floats; a different summation order after a
refactor or a parallel reduction; a `float` compared against a `Decimal`; a
value that round-tripped through JSON or a `float32`.

**Tell them apart by** printing both values with `repr` — `0.1 + 0.2` shows its
full expansion. Use `math.isclose` or `pytest.approx` with a tolerance that
matches the scale of the data, and use `Decimal` where money is involved.

## Memory grows and never comes back

**Usual causes** an unbounded cache — including `@lru_cache(maxsize=None)` on a
method, which keeps every `self` alive forever; a list or dict appended to on
every request; logging handlers added repeatedly; a reference cycle involving an
object with `__del__`; a C extension leaking outside Python's view.

**Tell them apart by** comparing two `tracemalloc` snapshots (§8 of the skill).
If the growth does not show up in `tracemalloc` at all, it is outside Python's
allocator and the suspect is a native library.

## The mock was not called

**Usual causes** patching the wrong path — `mock.patch` must target where the
name is *looked up*, not where it is defined, so a module doing
`from x import thing` needs `patch("consumer.thing")`, not `patch("x.thing")`;
patching after the object was already imported and bound; the code path never
running; an `AsyncMock` needed where a `Mock` was used.

**Tell them apart by** asserting the code path ran at all first — a print in the
function under test — before investigating the mock. Then print
`mock.mock_calls` rather than only asserting on it; the calls that *did* happen
usually identify the mistake immediately.
