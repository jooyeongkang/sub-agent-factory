# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A library of sub-agent definitions plus a compiler that renders them into the
formats different agent runtimes expect. Agents and skills are written once in a
canonical markdown format under `agents/` and `skills/`; `agent-factory`
validates them and emits runtime-specific trees into `dist/`.

opencode is the only implemented target so far, but the whole design exists to
support more — resist collapsing the canonical layer into opencode's format.

The library currently holds five agents (`code-refactor`, `code-reviewer`,
`debugger`, `docs-writer`, `test-writer`) and four skills (`code-refactor`,
`code-review`, `debugging`, `traceback-triage`). They are deliberately
specialised on Python, and the ones that shell out assume `uv run pytest`
rather than a bare `pytest`.

## Commands

```sh
make venv          # create .venv and pip install -r requirements.txt (which is -e .[dev])
make list          # every agent and skill, with descriptions
make test          # pytest
make validate      # schema-check every agent and skill
make build         # render into dist/<target>/
make install       # build, then copy into ~/.config/opencode/
make install-link  # same, but symlink (edits apply after a rebuild)
make uninstall-dry # show what an install would write and prune
make clean         # rm -rf dist
make distclean     # also rm -rf .venv, .pytest_cache, egg-info
```

Run a single test: `.venv/bin/pytest tests/test_builder.py::test_install_copies_and_prunes`

The CLI is `.venv/bin/agent-factory` (`targets`, `list`, `validate`, `build`,
`install`). It finds the repo root by walking up for a directory containing
`agents/`, so it works from any subdirectory; `--root` overrides.

End-to-end check against the real runtime, which is worth doing after touching
the opencode emitter:

```sh
agent-factory install --scope project --project-dir /tmp/probe
cd /tmp/probe && opencode agent list
```

## Architecture

The pipeline is one direction with three stages, and each has one module:

- `agent.py` — parses and validates one canonical file into an `Agent`. This is
  where the schema lives; there is no separate JSON Schema to keep in sync. It
  also owns the two primitives `skill.py` reuses, `NAME_RE` and
  `split_frontmatter`.
- `skill.py` — the same job for one `SKILL.md`. Kept separate rather than
  generalised: two formats is not enough evidence of a shared abstraction.
- `loader.py` — discovers `agents/**/*.md` and `skills/*/SKILL.md`, parses all of
  them, enforces global invariants (unique names).
- `targets/` — emitters. `base.Target` is the contract; `opencode.py` implements
  it; `__init__.py` is the registry.
- `builder.py` — renders a target's tree into `dist/` and installs it.
- `errors.py` — the exception hierarchy. `FileError` carries a path plus *every*
  problem found in that file; `LoadError` aggregates across files. The
  collect-then-raise shape of validation is a contract, not an implementation
  detail.
- `cli.py` — argparse wiring only; no logic worth testing lives here.

Adding a runtime means one `Target` subclass plus a line in `_TARGETS`. If a
change to support a new runtime requires touching `agent.py`, that field
probably belongs in the canonical schema rather than being special-cased.

### Invariants that are easy to break

**The build tree mirrors the runtime's config root, not its agent directory.**
`Target.output_path` returns `agent/<name>.md`, and `user_config_dir()` returns
`~/.config/opencode` — *not* `~/.config/opencode/agent`. Install is then a plain
copy of the tree with no path rewriting. Returning the agent subdirectory from
`user_config_dir()` silently produces `~/.config/opencode/agent/agent/foo.md`.

**Unspecified canonical fields must be absent from emitted frontmatter.** Use
`targets.base.put`, which skips `None` and empty dicts. Emitting `model: null`
would override the runtime's own default rather than inheriting it.

**Agents and skills carry identity in opposite ways, so `name` is emitted for
one and not the other.** An agent is identified by its filename, so
`OpencodeTarget.render` deliberately omits `name`. Every skill file is called
`SKILL.md` and the runtime checks the frontmatter `name` against the containing
directory, so `render_skill` must emit it. Dropping it there installs a skill
the runtime rejects.

**Install prunes via a manifest it wrote, and only that.** Each install drops
`.agent-factory.json` into the config root listing the files it placed; the next
install removes anything in that list it no longer produces, so deleting an
agent actually retires it. Files the factory never installed are left alone —
never widen pruning to "everything in the directory", which would eat a user's
hand-written agents. A retired skill also has its now-empty directory removed
(`_prune_empty_parents`), because the runtime lists an empty skill directory as
a broken skill.

**`dist/<target>/build-manifest.json` is build metadata, not installed output.**
`BuildResult.all_files` is what install acts on, and it lists rendered agents
and skills only. A build of the current library writes 13 files and installs 12.

### Canonical format notes

- `name` must equal the filename stem. opencode derives the agent id from the
  filename, so a mismatch would install the agent under a name it does not
  declare. This is validated, not silently reconciled.
- Unknown frontmatter keys are a hard error — catching typos like `modle:` is
  most of the value of validating at all. Free-form data goes under `meta:`,
  which is never emitted. (A skill's `metadata:` is a different field and *is*
  emitted; it is string-to-string only.)
- `targets:` restricts which runtimes emit an agent or skill; omitted means all.
  Nothing in the library uses it today, so a regression in that path will not be
  caught by building the real library — the tests cover it.
- A skill is a directory, not a file: `skills/<name>/SKILL.md`, with `name`
  matching the *directory*. Files beside `SKILL.md` — in practice
  `references/*.md` — are copied verbatim on build, because the runtime treats
  that directory as the skill's private base. Discovery is deliberately one
  level deep: `skills/a/b/SKILL.md` has no unambiguous name, so it is not found
  rather than being guessed at.
- `description` must be a single line *after* YAML parsing, so a folded scalar
  (`description: >-`) is the way to write a long one and is what most skills in
  this repo do. A literal block (`|`) keeps its newlines and is rejected.
- Validation collects every problem in a file before raising, and `load_agents`
  aggregates across files. Preserve that — reporting one error per run makes
  fixing a batch of agents miserable.
- Deprecated fields warn instead of failing (`tools:`, via `DEPRECATED_FIELDS`).
  Warnings are printed by the CLI to stderr and never block a build.

## opencode specifics

Verified against opencode 1.18.15 and <https://opencode.ai/config.json>:

- Agents are globbed as `{agent,agents}/**/*.md` under `~/.config/opencode` and
  a project's `.opencode/`. Both directory spellings work; this repo emits the
  singular `agent/`. `user_config_dir()` honours `XDG_CONFIG_HOME`.
- `tools` and `maxSteps` are deprecated upstream in favour of `permission` and
  `steps`. Both deprecated forms still pass through; `tools` emits a warning.
- `permission` values are `allow` / `ask` / `deny`, either bare or as a mapping
  of glob pattern to verdict. Tool names are deliberately not enumerated in
  validation — opencode adds tools faster than this repo can track.
- Skills are globbed as `skills/<name>/SKILL.md` under the same config roots as
  agents, so they install through the same tree copy with no new path logic.
  Loading one is gated by `permission.skill`, which takes a pattern mapping — an
  agent that should use a skill without prompting needs
  `permission: {skill: {"<skill-name>": allow}}`.
  The SKILL.md frontmatter is *not* described by `config.json` — it is a file
  format, documented at <https://opencode.ai/docs/skills>.

Check the config schema rather than reasoning from memory when changing the
emitter; the agent schema has moved more than once.

## Conventions

- Python 3.9-compatible (`from __future__ import annotations`, no `X | Y` at
  runtime, no builtin generics outside annotations, `"".format()` over f-strings
  to match surrounding code). `requires-python = ">=3.9"` in `pyproject.toml` is
  the source of truth; a newer interpreter in a dev container does not relax it.
- The only runtime dependency is PyYAML, and the only dev dependency is pytest.
  Keep it that way unless there is a real reason not to.
- Agent prompts in `agents/` and skill bodies in `skills/` are the product, not
  filler. Write them as instructions to a capable colleague: what is in scope,
  what standard of proof applies before reporting, and what to do when
  uncertain. Avoid padding them with generic advice the model already follows.
- A skill holds material a runtime loads on demand; an agent prompt is paid for
  on every call. Recipes, checklists, and catalogues belong in a skill.
- Tests use `tmp_path` and the `repo` fixture in `tests/conftest.py` rather than
  the real `agents/` tree, so adding or editing a library agent never breaks the
  suite. Keep new tests on that footing.
- `dist/` is generated and gitignored. Never hand-edit it.
