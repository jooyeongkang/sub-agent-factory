"""The canonical agent format: parsing and validation.

An agent lives in one markdown file: YAML frontmatter describing *how* the agent
is configured, and a body holding the system prompt. The format is deliberately
close to opencode's own agent schema so the opencode emitter is near-identity,
but it stays tool-neutral: repo-only bookkeeping lives under `meta`, and
`targets` decides which runtimes an agent is emitted for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .errors import AgentError

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODEL_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
MODES = ("subagent", "primary", "all")
PERMISSION_VALUES = ("allow", "ask", "deny")

#: Every key the canonical frontmatter accepts. Anything else is a typo and is
#: rejected, which is the whole point of having a schema at this layer.
KNOWN_FIELDS = frozenset(
    {
        "name",
        "description",
        "mode",
        "model",
        "variant",
        "temperature",
        "top_p",
        "steps",
        "color",
        "hidden",
        "disable",
        "permission",
        "tools",
        "targets",
        "meta",
    }
)

#: Accepted but discouraged. opencode marks these deprecated in its config
#: schema; we still pass them through so existing agents keep working.
DEPRECATED_FIELDS = {"tools": "use `permission` instead"}


@dataclass
class Agent:
    """A validated canonical agent definition."""

    name: str
    description: str
    prompt: str
    source: Path
    mode: str = "subagent"
    model: Optional[str] = None
    variant: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    steps: Optional[int] = None
    color: Optional[str] = None
    hidden: Optional[bool] = None
    disable: Optional[bool] = None
    permission: Dict[str, Any] = field(default_factory=dict)
    tools: Dict[str, bool] = field(default_factory=dict)
    targets: Optional[List[str]] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def applies_to(self, target_name: str) -> bool:
        """True when this agent should be emitted for `target_name`.

        `targets` omitted means "every target"; that is the common case, so
        agents only opt into a subset when they genuinely need to.
        """
        return self.targets is None or target_name in self.targets


def split_frontmatter(text: str) -> "tuple[str, str]":
    """Split a markdown file into its raw YAML frontmatter and body.

    Returns ("", text) when the file has no frontmatter block, letting the
    caller report the missing-frontmatter case with proper file context.
    """
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    # The opening fence is line 0; find the closing fence after it.
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return "", text


def parse_agent(path: Path) -> Agent:
    """Load and validate one agent file, or raise AgentError listing every problem."""
    text = path.read_text(encoding="utf-8")
    raw, body = split_frontmatter(text)

    if not raw.strip():
        raise AgentError(path, ["missing YAML frontmatter (file must start with `---`)"])

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise AgentError(path, ["invalid YAML frontmatter: {}".format(exc)])

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise AgentError(path, ["frontmatter must be a YAML mapping"])

    problems: List[str] = []
    warnings: List[str] = []

    unknown = sorted(set(data) - KNOWN_FIELDS)
    for key in unknown:
        problems.append(
            "unknown field `{}` (put free-form data under `meta:`)".format(key)
        )
    for key, advice in DEPRECATED_FIELDS.items():
        if key in data:
            warnings.append("`{}` is deprecated: {}".format(key, advice))

    stem = path.stem
    name = data.get("name")
    if name is None:
        problems.append("`name` is required")
    elif not isinstance(name, str):
        problems.append("`name` must be a string")
    elif not NAME_RE.match(name):
        problems.append("`name` must be kebab-case, got {!r}".format(name))
    elif name != stem:
        # opencode derives the agent id from the filename, so a mismatch would
        # silently install the agent under a different name than it declares.
        problems.append(
            "`name` is {!r} but the filename says {!r}; they must match".format(
                name, stem
            )
        )

    description = data.get("description")
    if description is None:
        problems.append("`description` is required (it drives delegation)")
    elif not isinstance(description, str) or not description.strip():
        problems.append("`description` must be a non-empty string")
    elif "\n" in description.strip():
        problems.append("`description` must be a single line")

    prompt = body.strip()
    if not prompt:
        problems.append("body is empty; it is the agent's system prompt")

    mode = data.get("mode", "subagent")
    if mode not in MODES:
        problems.append("`mode` must be one of {}, got {!r}".format(list(MODES), mode))

    model = data.get("model")
    if model is not None:
        if not isinstance(model, str):
            problems.append("`model` must be a string")
        elif not MODEL_RE.match(model):
            problems.append(
                "`model` must be `provider/model`, got {!r}".format(model)
            )

    for key in ("variant", "color"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            problems.append("`{}` must be a string".format(key))

    for key in ("temperature", "top_p"):
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append("`{}` must be a number".format(key))
        elif not 0.0 <= float(value) <= 1.0:
            problems.append("`{}` must be between 0.0 and 1.0, got {}".format(key, value))

    steps = data.get("steps")
    if steps is not None:
        if isinstance(steps, bool) or not isinstance(steps, int):
            problems.append("`steps` must be an integer")
        elif steps < 1:
            problems.append("`steps` must be >= 1, got {}".format(steps))

    for key in ("hidden", "disable"):
        value = data.get(key)
        if value is not None and not isinstance(value, bool):
            problems.append("`{}` must be a boolean".format(key))

    permission = data.get("permission")
    if permission is None:
        permission = {}
    elif not isinstance(permission, dict):
        problems.append("`permission` must be a mapping of tool -> rule")
        permission = {}
    else:
        problems.extend(_check_permission(permission))

    tools = data.get("tools")
    if tools is None:
        tools = {}
    elif not isinstance(tools, dict):
        problems.append("`tools` must be a mapping of tool -> boolean")
        tools = {}
    else:
        for tool, enabled in tools.items():
            if not isinstance(enabled, bool):
                problems.append("`tools.{}` must be a boolean".format(tool))

    targets = data.get("targets")
    if targets is not None:
        if not isinstance(targets, list) or not all(
            isinstance(t, str) for t in targets
        ):
            problems.append("`targets` must be a list of target names")
            targets = None
        elif not targets:
            problems.append("`targets` must not be empty (omit it to mean all targets)")
            targets = None

    meta = data.get("meta")
    if meta is None:
        meta = {}
    elif not isinstance(meta, dict):
        problems.append("`meta` must be a mapping")
        meta = {}

    if problems:
        raise AgentError(path, problems)

    return Agent(
        name=name,
        description=description.strip(),
        prompt=prompt,
        source=path,
        mode=mode,
        model=model,
        variant=data.get("variant"),
        temperature=data.get("temperature"),
        top_p=data.get("top_p"),
        steps=steps,
        color=data.get("color"),
        hidden=data.get("hidden"),
        disable=data.get("disable"),
        permission=permission,
        tools=tools,
        targets=targets,
        meta=meta,
        warnings=warnings,
    )


def _check_permission(permission: Dict[str, Any]) -> List[str]:
    """Validate permission rules.

    A rule is either a bare verdict ("allow"/"ask"/"deny") or a mapping of glob
    pattern to verdict. Tool names are not enumerated: opencode grows tools
    faster than this repo can track them, and an unknown key there is harmless.
    """
    problems: List[str] = []
    for tool, rule in permission.items():
        if isinstance(rule, str):
            if rule not in PERMISSION_VALUES:
                problems.append(
                    "`permission.{}` must be one of {}, got {!r}".format(
                        tool, list(PERMISSION_VALUES), rule
                    )
                )
        elif isinstance(rule, dict):
            for pattern, verdict in rule.items():
                if verdict not in PERMISSION_VALUES:
                    problems.append(
                        "`permission.{}[{}]` must be one of {}, got {!r}".format(
                            tool, pattern, list(PERMISSION_VALUES), verdict
                        )
                    )
        else:
            problems.append(
                "`permission.{}` must be a verdict string or a pattern mapping".format(
                    tool
                )
            )
    return problems
