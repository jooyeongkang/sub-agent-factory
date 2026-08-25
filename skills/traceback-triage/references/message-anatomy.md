# What each exception message hands you

A lookup for parsing the last line of a traceback. Each entry has two parts:

- **Hands you** — the facts the message actually encodes, which you get for free
  and which no amount of reading source can give you.
- **Then look for** — the search that turns those facts into a location.

This file is about *extraction*. For what usually causes a given symptom, load
the `debugging` skill and use its symptom index; the two are deliberately not
duplicated.

Jump to the exception you have. Reading this end to end is not the intended use.

## Contents

- [AttributeError](#attributeerror)
- [TypeError](#typeerror)
- [ValueError](#valueerror)
- [KeyError and IndexError](#keyerror-and-indexerror)
- [NameError and UnboundLocalError](#nameerror-and-unboundlocalerror)
- [ImportError and ModuleNotFoundError](#importerror-and-modulenotfounderror)
- [OSError and its subclasses](#oserror-and-its-subclasses)
- [Encoding errors](#encoding-errors)
- [JSONDecodeError](#jsondecodeerror)
- [ArithmeticError](#arithmeticerror)
- [StopIteration and RuntimeError](#stopiteration-and-runtimeerror)
- [RecursionError](#recursionerror)
- [AssertionError under pytest](#assertionerror-under-pytest)
- [Timeouts and connection errors](#timeouts-and-connection-errors)
- [pydantic ValidationError](#pydantic-validationerror)
- [Database errors](#database-errors)
- [Errors from another process or thread](#errors-from-another-process-or-thread)

## AttributeError

Three distinct forms that lead to three different searches.

```
AttributeError: 'Foo' object has no attribute 'bar'
```

**Hands you** the object's **actual runtime class**, which is the single highest
value fact available in any traceback. It says nothing about what you expected —
it reports what was there.

**Then look for**: is `Foo` the class you expected? If not, the bug is entirely
upstream of this line and this frame is innocent; go find where a `Foo` was
produced instead. If it is, then `bar` is set conditionally — search the class
for `self.bar` assignments and find the path that skips one, or check whether
`__init__` sets it only in a branch.

A suffix of `. Did you mean: 'baz'?` (3.10+) is Python's own spelling
suggestion, and it is right often enough to check first.

```
AttributeError: 'NoneType' object has no attribute 'bar'
```

**Hands you** the fact that something returned `None`. The problem is never on
this line; it is wherever that value came from.

**Then look for** the assignment of the receiver in this frame, and work
outwards. See §6 of the skill for the list of ways a `None` arrives.

```
AttributeError: module 'x' has no attribute 'y'
```

**Hands you** that `x` imported successfully but is not the `x` you meant, or is
not fully initialised.

**Then look for** a file named `x.py` in the working directory shadowing a real
module, a partially initialised module mid-circular-import, or a version where
the attribute moved. `x.__file__` settles it in one line.

## TypeError

```
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

**Hands you** both operand types **in order** — left operand first. That tells
you which side is wrong when only one of them is.

**Then look for** the source of the wrongly-typed side. A `str` where a number
belongs is nearly always unparsed input: an environment variable, a CSV field,
JSON, a CLI argument, a form value.

```
TypeError: 'NoneType' object is not subscriptable
TypeError: 'NoneType' object is not iterable
TypeError: 'NoneType' object is not callable
```

**Hands you** which operation was attempted: `x[...]`, unpacking or a `for`, and
a call respectively. With several expressions on the line, this picks one.

**Then look for**, in the `not callable` case specifically, a name rebound to
the result of a call — `foo = foo()` — or a decorator that returned `None`
because it forgot to return the wrapper.

```
TypeError: f() missing 1 required positional argument: 'x'
TypeError: f() got an unexpected keyword argument 'x'
TypeError: f() takes 2 positional arguments but 3 were given
```

**Hands you** the function's **runtime signature versus the call site**. The
"takes 2 but 3 were given" form counts `self`, so a method called with two
arguments reports three.

**Then look for** a version mismatch, a decorator that changed the signature, a
`functools.partial`, or an unbound method. Confirm with
`inspect.signature(thing)` rather than reading the definition — the definition
you are reading may not be the one that ran.

```
TypeError: '<' not supported between instances of 'NoneType' and 'int'
```

**Hands you** that a sort or comparison hit a `None` in the data.

**Then look for** the `sorted`/`min`/`max` call and the key function; a missing
field in one record out of thousands produces exactly this.

```
TypeError: unhashable type: 'list'
```

**Hands you** that a mutable object was used as a dict key or put in a set.

**Then look for** the construction of that key — often a list where a tuple was
meant, or a JSON-decoded array used as an identifier.

## ValueError

```
ValueError: invalid literal for int() with base 10: '12 '
```

**Hands you** the offending string **verbatim and `repr`-quoted**, so trailing
whitespace, a newline, a BOM (`'﻿12'`), an empty string, or a thousands
separator are all visible. Look inside the quotes before anything else — the
answer is often literally printed there.

```
ValueError: too many values to unpack (expected 2)
ValueError: not enough values to unpack (expected 3, got 2)
```

**Hands you** the expected arity, and in the second form the actual one too.

**Then look for** a row, line, or record that differs from the rest: a CSV line
with an extra comma, a `split(":")` on a value containing a colon, a header row,
a blank final line. The `got 2` form usually means one specific malformed input,
not a systematically wrong assumption.

```
ValueError: dictionary update sequence element #0 has length 1; 2 is required
```

**Hands you** that `dict()` or `.update()` was handed a flat sequence where it
wanted pairs — commonly a string instead of a mapping.

## KeyError and IndexError

```
KeyError: 'databse_url'
```

**Hands you** the exact key, `repr`-quoted. Read it character by character: the
typo, the case difference, the trailing space, or the `'1'`-versus-`1` type
mismatch is visible in the message itself. A `KeyError` with no quotes is a
non-string key, which is itself informative.

**Then look for** the literal in the source. If the key in the code matches the
key in the message exactly, the dict is the problem; if not, you already have
your answer.

```
IndexError: list index out of range
```

**Hands you** almost nothing — notably *not* the index or the length. This is one
of the least informative messages in Python.

**Then look for** the indexing expression on the cited line, and check the empty
case first: `[0]` on a result that legitimately found nothing accounts for most
of these. A `-1` on an empty list produces the same message.

```
IndexError: tuple index out of range
```

**Hands you** a strong hint that it is `%`-formatting or `str.format` with too
few arguments, rather than a data-structure bug.

## NameError and UnboundLocalError

```
NameError: name 'foo' is not defined
```

**Hands you** the name, and in 3.11+ often a `Did you mean:` suggestion.

**Then look for** an import inside a `try` that failed silently, a name defined
in another branch, or a typo. In a frame that is a comprehension or a lambda,
check the enclosing scope rules.

```
UnboundLocalError: cannot access local variable 'x' where it is not associated with a value
```

**Hands you** something quite specific: `x` **is** assigned somewhere in this
function, which is what makes it local, but the assignment did not run before
this read.

**Then look for** an assignment inside an `if` or a loop body that did not
execute, or a read before assignment where a global of the same name was
intended — the missing `global`/`nonlocal` declaration is the classic.

## ImportError and ModuleNotFoundError

```
ModuleNotFoundError: No module named 'foo'
```

**Hands you** the top-level name that failed. `No module named 'foo.bar'` versus
`'foo'` matters: the first means `foo` was found and `bar` was not.

```
ImportError: cannot import name 'thing' from partially initialized module 'x'
(most likely due to a circular import)
```

**Hands you** the diagnosis outright, plus the module that was mid-import.

**Then look for** the import chain in the traceback frames above — they list the
cycle in order. Note that `from x import thing` fails where `import x` would
have succeeded, because it resolves the name immediately.

```
ImportError: cannot import name 'thing' from 'x' (/path/to/x.py)
```

**Hands you** the resolved path in parentheses. Check it. If it is not the file
you have been editing, that is the entire bug.

## OSError and its subclasses

```
FileNotFoundError: [Errno 2] No such file or directory: 'data/input.csv'
IsADirectoryError: [Errno 21] ...
PermissionError: [Errno 13] ...
OSError: [Errno 28] No space left on device
```

**Hands you** the errno, the OS's own description, and the **exact path as
resolved**. A relative path means the working directory is part of the bug — the
same code run from a different directory would behave differently.

**Then look for**, when the path looks right, whether it is being resolved
relative to the process's cwd rather than to the module. `Path(__file__).parent`
versus a bare relative string is the usual distinction.

`[Errno 2]` on a path that clearly exists is often a broken symlink, a missing
*interpreter* for a script being executed, or a missing shared library rather
than the named file.

## Encoding errors

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x92 in position 4721:
invalid start byte
```

**Hands you** the codec that was used, the offending byte, and the exact byte
offset. `0x92`, `0x93`, `0x94` are curly quotes in cp1252 — a strong signal the
file came from Excel or Word. A failure at position 0 with `0xff` or `0xfe` is a
UTF-16 BOM.

**Then look for** the `open()` call with no explicit `encoding`, which uses the
platform default. Inspect the raw bytes around the reported position before
choosing a codec.

```
UnicodeEncodeError: 'ascii' codec can't encode character '’' in position 12
```

**Hands you** the character and the target codec. An `ascii` target usually means
a C locale in a container or CI, not a decision anyone made.

## JSONDecodeError

```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Hands you** that the very first character was not valid JSON — so the body was
almost certainly **empty**, or HTML, or a plain-text error page. This is a
network or auth failure wearing a parsing error's clothes.

**Then look for** the response before the parse: log or print `response.status_code`
and the first 200 bytes of the body. Do not debug the parser.

Other positions (`line 1 column 4573`) mean genuinely malformed JSON, most often
truncation from a dropped connection or a size limit.

## ArithmeticError

```
ZeroDivisionError: division by zero
ZeroDivisionError: float division by zero
```

**Hands you** whether the operands were integers or floats, which narrows which
expression on the line it was.

**Then look for** an average or rate over an empty collection — `total / len(xs)`
where `xs` is empty is the overwhelming majority of these.

```
OverflowError: math range error
ValueError: math domain error
```

**Hands you** that the input to a `math` function was outside its domain —
`sqrt` or `log` of a negative, `acos` of something above 1. Floating-point drift
producing `1.0000000000000002` for a value that should be exactly `1.0` is a
common source.

## StopIteration and RuntimeError

```
RuntimeError: generator raised StopIteration
```

**Hands you** that a `StopIteration` escaped from inside a generator body,
which Python converts (PEP 479). The underlying cause is usually a bare `next()`
with no default inside a generator.

**Then look for** `next(` in the generator and give it a default.

```
RuntimeError: dictionary changed size during iteration
RuntimeError: Set changed size during iteration
```

**Hands you** the container kind. Note it fires on **size** change, so
reassigning existing keys does not trigger it — something was added or deleted.

```
RuntimeError: Event loop is closed
RuntimeError: This event loop is already running
RuntimeError: no running event loop
```

**Hands you** which of three distinct async mistakes it is: use after shutdown,
a nested `asyncio.run`, and a coroutine-creating call from synchronous context
respectively.

## RecursionError

```
RecursionError: maximum recursion depth exceeded while calling a Python object
```

**Hands you**, in the frames rather than the message, the **repeating unit**.
Look at the cycle above `[Previous line repeated 996 more times]`: two or three
alternating frames is mutual recursion with no base case; a single frame
repeated is genuine depth.

**Then look for** `__getattr__` that touches a missing attribute on `self`, or
`__eq__`/`__repr__` walking a cyclic structure — these produce a very short
repeating cycle and are the most common instances.

## AssertionError under pytest

```
E       assert 3 == 4
E        +  where 3 = len([1, 2, 3])
```

**Hands you** pytest's rewritten assertion detail: the `+ where` lines expand
each sub-expression to its actual value. This is a set of runtime values handed
to you for free, and it is frequently enough on its own.

A bare `E  AssertionError` with no expansion means the assertion was in a helper
module pytest did not rewrite, or it had an explicit message. Ask for `-l` to
recover the locals instead.

For long comparisons, `E  ...Full output truncated (N lines hidden), use '-vv'` —
ask for `-vv` before speculating about which element differs.

## Timeouts and connection errors

```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.example.com',
port=443): Max retries exceeded with url: /v1/items (Caused by
NewConnectionError(...: [Errno -2] Name or service not known))
```

**Hands you** the host, port, path, and — inside the innermost parenthesised
cause — the actual network fault. Read the innermost one: `Name or service not
known` is DNS, `Connection refused` is nothing listening, `certificate verify
failed` is TLS, and a timeout is reachability. These have nothing to do with one
another.

**Then look for** the host name itself. A hostname that resolves for you and not
in CI, or a `localhost` inside a container, is the whole bug.

## pydantic ValidationError

```
2 validation errors for Config
database.port
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='5432 ', input_type=str]
```

**Hands you** an unusually complete report: the model, the **dotted path to each
bad field**, the failing rule, and `input_value` as a `repr` — a trailing space
or an empty string is visible directly. It also tells you the error **count**,
so a single field failing versus every field failing distinguishes a bad value
from a wholly wrong payload shape.

**Then look for** the source of that one field, using the dotted path. Do not
read the model definition first; the message already told you which field.

## Database errors

```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation) duplicate key
value violates unique constraint "users_email_key"
DETAIL:  Key (email)=(a@b.com) already exists.
[SQL: INSERT INTO users ...] [parameters: {...}]
```

**Hands you** the driver's own error nested inside the ORM's, the **constraint
name**, the offending value in `DETAIL`, and the full statement with its bound
parameters. The constraint name identifies the exact column; the parameters show
what was actually sent, which is the value you would otherwise go hunting for.

**Then look for** the wrapped driver exception in parentheses first — the ORM
layer's class (`IntegrityError`, `DataError`, `OperationalError`) is a category,
and the driver's class inside it is the specific fault.

```
sqlalchemy.orm.exc.DetachedInstanceError
```

**Hands you** that an ORM object outlived its session, which is a lifetime bug
rather than a query bug — look at where the session is closed, not at the model.

## Errors from another process or thread

```
concurrent.futures.process.BrokenProcessPool: A process in the process pool was
terminated abruptly while the future was running or pending.
```

**Hands you** that the child died without raising — so it segfaulted, was OOM
killed, or called `os._exit`. There is no Python-level cause to find in this
traceback, because there is no Python-level cause.

**Then look for** the child's own output: the pool swallows it. Re-run the
failing work in-process to get a real traceback.

Where a worker raised normally, the message often contains the **remote
traceback as embedded text**. Read that text as a traceback in its own right,
with everything in this file — it, not the wrapper, is the actual failure.
