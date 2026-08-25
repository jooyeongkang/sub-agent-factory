# sub-agent-factory

One place to write sub-agents and the skills that support them, compiled out to
whichever agent runtime you use.

Each agent is a single markdown file: YAML frontmatter for configuration, body
for the system prompt. Each skill is a directory holding a `SKILL.md` and any
supporting files. `agent-factory` validates them against a schema and renders
them into the exact on-disk layout a runtime expects.

opencode is the currently supported target.

## Quick start

```sh
make venv        # create .venv and install the CLI
make validate    # check every agent against the schema
make build       # render into dist/opencode/
make install     # copy into ~/.config/opencode/
```

Then `opencode agent list` shows them.

Prefer `make install-link` while iterating: it symlinks instead of copying, so
a `make build` is enough to push changes through.

## Writing an agent

Create `agents/<name>.md`. The filename is the agent's identity — opencode
derives the agent id from it, so `name` in the frontmatter must match the
filename stem.

```markdown
---
name: code-reviewer
description: Reviews a diff for correctness bugs and reports findings
mode: subagent
temperature: 0.1
permission:
  edit: deny
  bash:
    "*": ask
    "git diff*": allow
meta:
  tags: [review]
---

You review code and report what you find. You do not change it.
...
```

Subdirectories under `agents/` are fine and are for your own organisation only;
they do not affect the agent's name or where it installs.

### Frontmatter fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | **Required.** kebab-case, must equal the filename stem. |
| `description` | string | **Required.** One line. This is what the calling model reads to decide when to delegate, so make it concrete. |
| `mode` | `subagent` \| `primary` \| `all` | Defaults to `subagent`. |
| `model` | string | `provider/model`. Omit to inherit the runtime's default. |
| `variant` | string | Model variant, when the model supports one. |
| `temperature` | number | 0.0–1.0. |
| `top_p` | number | 0.0–1.0. |
| `steps` | integer | Max agentic iterations before a text-only response. |
| `color` | string | Hex (`#FF5733`) or a theme colour name. |
| `hidden` | boolean | Hide from the `@` autocomplete menu. Subagents only. |
| `disable` | boolean | Build it, but leave it switched off. |
| `permission` | mapping | Tool → `allow`/`ask`/`deny`, or tool → {glob → verdict}. |
| `tools` | mapping | Tool → boolean. **Deprecated** upstream; use `permission`. |
| `targets` | list | Restrict which targets emit this agent. Omit to mean all. |
| `meta` | mapping | Free-form repo bookkeeping (tags, notes). Never emitted. |

Anything else is rejected as a typo — that is the point of validating.

The body is the system prompt, and must not be empty.

## Writing a skill

Skills hold reference material a runtime loads on demand, rather than material
that sits in a system prompt on every call. They are the right home for command
recipes, checklists, and catalogues an agent only sometimes needs.

A skill is a *directory*, because the runtime treats that directory as the
skill's private base and every skill file is called `SKILL.md`:

```
skills/
  code-refactor/
    SKILL.md
    references/          # optional, copied verbatim on build
      notes.md
```

```markdown
---
name: code-refactor
description: Reference for behaviour-preserving Python refactoring - baselines, characterisation tests, and the changes that look safe but are not.
meta:
  tags: [refactoring]
---

Working material for restructuring Python without changing what it does.
...
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | **Required.** kebab-case, ≤64 chars, must equal the *directory* name. |
| `description` | string | **Required.** One line, ≤1024 chars. This is what the model reads to decide whether to load the skill. |
| `license` | string | Optional. |
| `compatibility` | string or mapping | Optional. Runtime compatibility hints. |
| `metadata` | mapping | Optional. String → string only; emitted to the runtime. |
| `targets` | list | Restrict which targets emit this skill. Omit to mean all. |
| `meta` | mapping | Free-form repo bookkeeping. Never emitted. |

The identity rule is the same idea as an agent's, moved up one level: an agent
is named by its filename, a skill by its directory. Because of that, `name` **is**
emitted into a skill's frontmatter, where an agent's deliberately is not.

To let an agent load a skill without prompting, grant it in the agent's
frontmatter:

```yaml
permission:
  skill:
    "code-refactor": allow
```

## Commands

```sh
agent-factory targets       # supported runtimes
agent-factory list          # every agent and skill, with descriptions
agent-factory list --json   # same, machine-readable
agent-factory validate      # schema check, reports all problems at once
agent-factory build         # render into dist/
agent-factory install       # build, then place into the runtime's config
```

`install` takes `--scope user` (default, `~/.config/opencode`) or
`--scope project --project-dir <path>` (`<path>/.opencode`), plus `--link` to
symlink, `--dry-run` to preview, and `--dest` to override the location.

Install writes a `.agent-factory.json` manifest into the config root recording
what it placed there. The next install removes files listed in it that are no
longer produced, so deleting an agent from `agents/` actually retires it.
Files the factory never installed are left alone.

## Adding another runtime

Subclass `Target` in `src/agent_factory/targets/`, implement `render`,
`user_config_dir`, and `project_config_dir`, and add an instance to `_TARGETS`
in `targets/__init__.py`. Nothing else needs to change.

For a runtime with a skill concept, also set `skills_subdir` and implement
`render_skill`. A target that leaves `skills_subdir` empty simply emits no
skills, so it costs nothing to ignore.

Agents and skills can then opt in or out per runtime with `targets:`.
