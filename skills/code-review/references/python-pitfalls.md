# Python failure modes: what to look for, how to confirm, when to let it go

The agent prompt lists these categories; this file is the working detail. Each
entry has the same three parts:

- **Looks like** — the shape on the page that should make you slow down.
- **Confirm by** — what to check before it counts as a finding. Skipping this is
  how a review turns into a list of things that pattern-matched.
- **Not a bug when** — the cases where the same shape is correct, so you can
  drop it fast instead of hedging in the report.

Use it as a lookup when something looks off. Walking it top to bottom on every
review produces padded reports and wastes the reader's attention.

## Contents

- [State that outlives the call](#state-that-outlives-the-call)
- [Closures and loops](#closures-and-loops)
- [Exception handling](#exception-handling)
- [Truthiness and identity](#truthiness-and-identity)
- [Mutation and aliasing](#mutation-and-aliasing)
- [Iterators and generators](#iterators-and-generators)
- [Resources](#resources)
- [Equality, hashing, and comparison](#equality-hashing-and-comparison)
- [Async](#async)
- [Datetimes](#datetimes)
- [Injection and trust boundaries](#injection-and-trust-boundaries)
- [Type hints that lie](#type-hints-that-lie)
- [Concurrency](#concurrency)

## State that outlives the call

**Looks like**

```python
def add(item, bucket=[]):          # evaluated once, at def time
class Job:
    handlers = {}                  # shared by every instance
```

**Confirm by** finding a write to it — `bucket.append(...)`, `self.handlers[k] = v`
(note that this one rebinds nothing; it mutates the class-level dict). Then check
whether the function or class is called more than once in a process. A CLI that
constructs one object and exits may never expose it.

**Not a bug when** the default is only read, or is immutable (`()`, `None`, a
frozen dataclass), or the class attribute is a genuine constant. Read-only
mutable defaults are still worth a one-line minor note — the next edit will
mutate them.

## Closures and loops

**Looks like**

```python
callbacks = [lambda: print(i) for i in range(3)]     # all print 2
handlers = {name: lambda: send(name) for name in names}
```

**Confirm by** checking whether the closure is *called* after the loop finishes.
If it is invoked inside the loop body, late binding never bites.

**Not a bug when** the loop variable is bound as a default argument
(`lambda i=i: ...`), captured via `functools.partial`, or the callables run
immediately.

## Exception handling

**Looks like** `except:` bare, `except Exception: pass`, `return` or `break`
inside `finally`, `except` blocks that log at debug level and continue.

**Confirm by** asking what the caller now sees. A swallowed exception is a
finding when the caller proceeds as if the operation succeeded — the write did
not land, the cache was not populated, but the function returned normally. Also
check `finally`: a `return` there discards an in-flight exception entirely,
which silently converts a crash into a wrong value.

Bare `except:` additionally catches `KeyboardInterrupt` and `SystemExit`, so a
retry loop wrapped in one cannot be interrupted.

**Not a bug when** the handler logs and re-raises, converts to a domain
exception, or sits at a deliberate boundary (task runner, request handler,
plugin loader, cleanup path) where continuing is the intended behaviour and the
failure is recorded somewhere.

## Truthiness and identity

**Looks like** `if not value:`, `if items:`, `value = arg or default`.

**Confirm by** working out whether `0`, `0.0`, `""`, `[]`, `{}`, or `False` is a
legitimate value distinct from "not provided". `timeout = timeout or 30` turns
an explicit `timeout=0` into 30. `if not count:` treats a real count of zero as
missing.

**Not a bug when** the value is known to be a `bool`, or when the falsy cases
genuinely deserve the same handling as `None` — which is often true for
"is there anything to do here" checks over collections.

## Mutation and aliasing

**Looks like**

```python
for item in items:
    if item.stale:
        items.remove(item)         # skips elements

def normalise(config):
    config["path"] = resolve(config["path"])    # caller's dict
    return config
```

**Confirm by** for mutation-during-iteration, confirming the collection being
mutated is the one being iterated (not a copy, not `list(items)`). For aliasing,
checking whether the caller uses the argument after the call and whether it
expects it unchanged — a returned value plus an in-place mutation is a
particularly easy trap, since the caller reasonably assumes the return is the
only output.

Watch `dict` too: mutating during iteration raises `RuntimeError` rather than
silently skipping, which is at least loud.

**Not a bug when** the mutation is documented and intended (`list.sort()`-style
APIs), or iteration is over a snapshot (`for item in list(items)`), or the
object was constructed locally.

## Iterators and generators

**Looks like**

```python
rows = (parse(line) for line in f)
if not rows:                      # always falsy-checks the generator object, not its contents
count = len(rows)                 # TypeError
for r in rows: ...                # second loop over the same generator yields nothing
```

**Confirm by** tracing every use of the value. Generators, `map`, `filter`,
`zip`, and `dict.items()` views behave differently from lists at exactly these
points. A generator object is always truthy, so `if not rows:` never fires.

**Not a bug when** the iterator is consumed exactly once, or materialised with
`list(...)` before the second use.

## Resources

**Looks like** `open(...)`, `socket(...)`, `subprocess.Popen(...)`,
`session()`, `acquire()` without a `with` block or a `try/finally`.

**Confirm by** finding the guaranteed close. Follow ownership: the object may be
closed by a fixture, a dependency-injection scope, a context manager the caller
holds, or an `__exit__` further up. Also check the error path specifically — a
`close()` on the happy path only is still a leak when an exception intervenes.

`subprocess` deserves its own look: an unwaited process becomes a zombie, and
`communicate()` is what prevents a pipe deadlock when output is large.

**Not a bug when** ownership is clearly elsewhere, or the object is returned to
the caller who is expected to close it (worth confirming the caller does).

## Equality, hashing, and comparison

**Looks like** `__eq__` defined without `__hash__`, `==` on floats,
`is` on ints or strings, `sort()` on mixed types.

**Confirm by** checking use: defining `__eq__` sets `__hash__` to `None`, so the
instance becomes unhashable — a finding only if it is used in a set or as a dict
key. For floats, check whether the values come from arithmetic (accumulated
error) or are exact literals passed through. `is` comparisons on small ints and
interned strings work by accident and break on values outside the cache — the
usual trigger is a value read from input or computed at runtime.

**Not a bug when** the dataclass decorator generates both (`frozen=True` or
`eq=True, frozen=True`), or the `is` comparison is against `None`, `True`,
`False`, or a sentinel object.

## Async

**Looks like**

```python
result = fetch(url)               # coroutine never awaited
time.sleep(5)                     # inside async def — blocks the loop
asyncio.create_task(work())       # return value dropped
requests.get(url)                 # sync I/O in an async function
```

**Confirm by** checking the definition of the callee — `async def` means the
call needs `await`, and an un-awaited coroutine produces a `RuntimeWarning` and
no work at all. For dropped tasks, check whether a reference is retained; tasks
held only by the event loop can be garbage collected mid-flight, and exceptions
inside them are never observed.

Also look at state read before an `await` and written after it: the loop can run
other work in between, so the read may be stale in a way that is invisible
without concurrency in mind.

**Not a bug when** the function is deliberately synchronous, the blocking call
is wrapped in `run_in_executor` / `asyncio.to_thread`, or the task reference is
stored in a set that outlives it.

## Datetimes

**Looks like** `datetime.now()`, `datetime.utcnow()`, subtracting two datetimes
from different sources, `.replace(tzinfo=...)` on a local time.

**Confirm by** determining awareness at each site. Comparing or subtracting a
naive and an aware datetime raises `TypeError`; comparing two naives from
different zones silently gives a wrong answer, which is worse. `utcnow()` returns
a *naive* datetime that looks like UTC — a persistent source of off-by-hours
bugs; `datetime.now(timezone.utc)` is the correct form.

Storage boundaries are where this bites: what the database column holds, what
the API serialises, what the parser produces.

**Not a bug when** the codebase is consistently naive-UTC by convention and the
new code follows it — note the convention rather than reporting the instance.

## Injection and trust boundaries

**Looks like**

```python
subprocess.run(f"git log {ref}", shell=True)
cursor.execute("SELECT * FROM t WHERE id = %s" % user_id)
yaml.load(payload)                # without SafeLoader
pickle.loads(blob)
open(os.path.join(root, name))    # name may contain ".."
eval(expr)
```

**Confirm by** tracing the value back to its origin. This is the whole job here:
a constructed shell string built from a hardcoded constant is fine; the same
line fed by an HTTP parameter is critical. Follow it through the call chain
until you reach either a literal or a boundary (request, file, env var, database
row, message queue). If it reaches a boundary, check for validation in between —
and check that the validation actually constrains it (a regex allowing `.` in a
path component does not stop traversal).

Note severity honestly: reachable from untrusted input is a critical finding;
reachable only from an operator-supplied config is worth reporting at low
severity with that caveat stated.

**Not a bug when** parameters are properly bound (`execute(sql, (id,))`),
`shell=False` with a list argv, `yaml.safe_load`, or the path is confined by a
resolved-prefix check (`Path(root).resolve()` compared against
`candidate.resolve()`).

## Type hints that lie

**Looks like** a signature promising `-> str` with a branch returning `None`;
`Optional[T]` dereferenced without a check; `-> list` returning a generator;
`dict` annotated but a custom mapping returned.

**Confirm by** reading every `return` in the function, including implicit ones —
a function whose `if` chain has no `else` returns `None` on the fall-through
path. Then check whether a caller does something that breaks on that value
(`len()`, attribute access, string concatenation).

**Not a bug when** the project does not run a type checker and the annotation is
decorative — still worth a minor note, since the next reader will trust it. If a
type checker is in CI, treat a lying annotation as a correctness finding: the
callers were written against a guarantee that does not hold.

## Concurrency

**Looks like** shared mutable state touched from threads, check-then-act
sequences (`if key not in cache: cache[key] = compute()`), a lock acquired on one
path and not another, `multiprocessing` with objects that do not pickle.

**Confirm by** identifying the threads or processes that actually exist. Much
apparently-shared state is only ever touched by one thread, which makes the race
theoretical. When there are genuinely concurrent writers, name them in the
finding — "the request handler and the background refresh task both write
`self._cache`" is checkable; "this is not thread-safe" is not.

**Not a bug when** the state is thread-local, guarded by a lock across all
paths, confined to one thread, or the operation is atomic by virtue of the GIL
in a way the code clearly relies on (a single `dict.__setitem__`, for example) —
though relying on that implicitly is worth a note.
