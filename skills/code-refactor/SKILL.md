---
name: code-refactor
description: Reference for behaviour-preserving Python refactoring - how to establish a pytest baseline under uv, write characterisation tests when coverage is missing, avoid the changes that look safe but alter behaviour, and audit your own diff before reporting.
meta:
  tags: [refactoring, python, quality]
---

Working material for restructuring Python without changing what it does. Read
the section you need; you do not need all of it for every job.

## Establishing a baseline

You cannot prove you preserved behaviour without knowing what the behaviour was.
Get a passing test run before you edit anything, and keep the output.

Projects here use **uv**. Run everything through it so you get the project's
pinned dependencies and its Python version:

```sh
uv sync
uv run pytest -q
```

Save the baseline somewhere you can compare against later:

```sh
uv run pytest -q > /tmp/baseline.txt 2>&1
```

Then narrow to the code you are about to touch, which is the run you will repeat
most often:

```sh
uv run pytest tests/test_thing.py -q
```

Never call `pytest` or `python` on their own. Outside `uv run` you may be on a
different interpreter with different packages installed, and a green run there
proves nothing about the project. If the repo has a `Makefile` or `tox.ini`
target for tests, prefer it — it carries flags and settings you would otherwise
miss.

Useful during the work:

| Command | Use |
|---|---|
| `uv run pytest -x -q` | Stop at the first failure while iterating. |
| `uv run pytest --lf` | Re-run only what failed last time. |
| `uv run pytest -p no:randomly` | Rule out ordering effects. |
| `uv run python -m compileall -q <path>` | Catch syntax errors fast, without running tests. |
| `uv run mypy .` / `uv run pyright` | Catch signature mistakes tests miss. |
| `uv run ruff check .` / `uv run black .` | Only if the repo already configures them. |

If `uv sync` fails, stop and report it. Do not fall back to `pip`, and do not
create a virtualenv by hand — a different environment invalidates the baseline.

## When nothing covers the code

Refactoring untested code is the main way this job goes wrong. If the target has
no tests, offer to write characterisation tests first.

A characterisation test records what the code does **today**, including
behaviour that looks wrong. It is not a statement that the behaviour is correct;
it is a tripwire that fires if you change it.

The recipe:

1. Find the real inputs. Pull them from callers, fixtures, logs, or the
   docstring — invented inputs test invented behaviour.
2. Call the function and print what comes back, rather than guessing.
   ```sh
   uv run python -c "from mypkg.thing import parse; print(repr(parse('sample')))"
   ```
3. Paste the observed value into an assertion, exactly as printed. Use `repr`
   output so type differences show up.
4. Do the same for the ugly paths: what it raises on bad input, what it writes,
   what it logs. `pytest.raises`, `tmp_path`, and `caplog` cover most of this.
5. Run the new tests and watch them pass **before** you refactor. A
   characterisation test that was never green is worthless.

If something looks like a bug while you are doing this, pin the buggy behaviour
in the test, add a comment saying it looks wrong, and report it. Do not fix it.

When the caller declines characterisation tests, get explicit agreement that
your only check will be careful reading, and say so again in your final report.

## What to change, in priority order

- **Structure before syntax.** Split a function that does four separate things.
  Give a name to a condition nobody can read. Turn three copies of one block
  into a helper with a parameter. Rewriting a loop as a comprehension because
  comprehensions are idiomatic is not worth a diff.
- **Let the shape fit the data.** A dict of dicts threaded through six functions
  usually wants to be a `dataclass`. Several lists kept in step usually want to
  be one list of records.
- **Remove real duplication only.** Real duplication is code that must change in
  both places for the same reason. Two functions that merely look alike are not
  duplicates, and merging them couples things that need to move apart later.
- **Use idioms that remove noise, not ones that show off.** `enumerate` and
  `zip` instead of index arithmetic; `pathlib` instead of string surgery on
  paths; a context manager instead of `try`/`finally`; the right `collections`
  type instead of a hand-built one.

Delete dead code only after checking it really is dead. Grep for the name as
text, not just as an import — Python reaches names through `getattr`, plugin
registries, entry points, and strings in config files.

## Changes that look safe and are not

Each of these reads as tidying and quietly changes behaviour.

**Data and iteration**

- **List to generator, or generator to list.** Changes memory use, when the work
  happens, and whether the caller can iterate twice or call `len()`.
- **Building a dict or set in a different order.** Dict order is insertion order
  and callers observe it — in printed output, in JSON, in test assertions.
- **Sorting where there was no sort**, or dropping one that looked redundant.
- **Returning a copy instead of the original object**, or the reverse. Callers
  that mutate the result will silently change meaning.

**Truthiness and identity**

- **Swapping `is` for `==`, or rewriting `if x:` as `if x is not None:`.** These
  agree on most values and disagree on `0`, `""`, `[]`, and NaN.
- **Collapsing `if x is None: x = default` into `x = x or default`.** Same trap,
  and it is the most common way this one gets in.

**Structure and imports**

- **Moving an import between module level and inside a function.** Module-level
  imports run at import time, which can break a deliberate circular-import
  workaround or change when a side effect fires.
- **Turning a method into a `@property` or back.** Changes the call syntax at
  every call site, and the behaviour under `getattr` and `hasattr`.
- **Renaming or moving anything public.** Public means listed in `__all__`,
  re-exported from an `__init__.py`, named as an entry point in
  `pyproject.toml`, or imported from outside the package.

**Errors and defaults**

- **Widening or narrowing an `except` clause, or raising a different type.**
- **Changing a default argument.** Replacing a shared mutable default such as
  `xs=[]` with `None` fixes a genuine bug — which is exactly why it is not part
  of a refactor. Report it and leave it.
- **Reordering parameters, or turning positional into keyword-only.**

**Dunder methods and output**

- **Adding or changing `__slots__`, `__eq__`, or `__hash__`.** Defining `__eq__`
  without `__hash__` makes instances unhashable.
- **Rewording any string** that reaches a log, a `repr`, an error message, or
  serialised output. Something is probably asserting on it.

## Auditing your own diff

Tests only cover what tests cover. Before reporting, read the whole diff:

```sh
git diff
```

Take each hunk and ask four questions:

1. Could this change a value that gets returned?
2. Could this change which exception is raised, or its message?
3. Could this change something written out — a file, a log line, a response, a
   printed string?
4. Could this change the order in which things happen, or how many times?

If a hunk makes you hesitate on any of them, revert that hunk. The refactor is
worth less than the certainty.

Then re-run the baseline command and compare against the saved output:

```sh
uv run pytest -q > /tmp/after.txt 2>&1
diff /tmp/baseline.txt /tmp/after.txt
```

Same set of tests, same count, same result. A test that vanished from the run is
as much of a problem as one that failed.

## Reporting

Close with these four things, briefly:

- **What changed**, and why it is better. Name the files.
- **What you deliberately left alone**, and why — code you judged too risky
  without coverage, duplication that was not real duplication.
- **What you could not verify.** Anything checked by reading rather than by
  tests belongs here.
- **Any bug you found and did not fix**, described well enough to act on:
  where it is, what input triggers it, what happens.

If the suite was not green before you started, say that first. It changes how
much a green run at the end is worth.
