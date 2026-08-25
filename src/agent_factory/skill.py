"""The canonical skill format: parsing and validation.

A skill is a *directory* containing `SKILL.md` -- YAML frontmatter naming and
describing the skill, and a body holding the reference material a runtime loads
on demand. Supporting files may sit alongside it in the same directory.

This mirrors how the runtimes themselves store skills, and it is why identity
works differently here than for agents: every skill file is called `SKILL.md`,
so the *directory* name carries the name, and `name` must be emitted into the
frontmatter rather than left implicit.

Verified against https://opencode.ai/docs/skills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .agent import NAME_RE, split_frontmatter
from .errors import SkillError

#: The filename a skill directory must contain.
SKILL_FILENAME = "SKILL.md"

#: The runtime advertises descriptions to the model verbatim and caps them here.
MAX_DESCRIPTION = 1024

#: Every key the canonical frontmatter accepts. opencode ignores keys it does
#: not know, but a typo silently losing a field is exactly what this layer is
#: for, so unknown keys stay a hard error.
KNOWN_FIELDS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "targets",
        "meta",
    }
)


@dataclass
class Skill:
    """A validated canonical skill definition."""

    name: str
    description: str
    body: str
    source: Path
    directory: Path
    #: Supporting files beside SKILL.md, relative to `directory`, copied verbatim.
    extra_files: List[Path] = field(default_factory=list)
    license: Optional[str] = None
    compatibility: Optional[Any] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    targets: Optional[List[str]] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def applies_to(self, target_name: str) -> bool:
        """True when this skill should be emitted for `target_name`.

        `targets` omitted means "every target", matching agent behaviour.
        """
        return self.targets is None or target_name in self.targets


def parse_skill(path: Path) -> Skill:
    """Load and validate one `SKILL.md`, or raise SkillError listing every problem."""
    text = path.read_text(encoding="utf-8")
    raw, body = split_frontmatter(text)

    if not raw.strip():
        raise SkillError(path, ["missing YAML frontmatter (file must start with `---`)"])

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SkillError(path, ["invalid YAML frontmatter: {}".format(exc)])

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SkillError(path, ["frontmatter must be a YAML mapping"])

    problems: List[str] = []

    unknown = sorted(set(data) - KNOWN_FIELDS)
    for key in unknown:
        problems.append(
            "unknown field `{}` (put free-form data under `meta:`)".format(key)
        )

    directory = path.parent
    name = data.get("name")
    if name is None:
        problems.append("`name` is required")
    elif not isinstance(name, str):
        problems.append("`name` must be a string")
    elif not NAME_RE.match(name):
        problems.append("`name` must be kebab-case, got {!r}".format(name))
    elif len(name) > 64:
        problems.append("`name` must be at most 64 characters, got {}".format(len(name)))
    elif name != directory.name:
        # Every skill file is called SKILL.md, so the directory is the only
        # thing carrying identity; a mismatch installs the skill under a name it
        # does not declare.
        problems.append(
            "`name` is {!r} but the directory says {!r}; they must match".format(
                name, directory.name
            )
        )

    description = data.get("description")
    if description is None:
        problems.append("`description` is required (it drives when the skill loads)")
    elif not isinstance(description, str) or not description.strip():
        problems.append("`description` must be a non-empty string")
    elif "\n" in description.strip():
        problems.append("`description` must be a single line")
    elif len(description.strip()) > MAX_DESCRIPTION:
        problems.append(
            "`description` must be at most {} characters, got {}".format(
                MAX_DESCRIPTION, len(description.strip())
            )
        )

    content = body.strip()
    if not content:
        problems.append("body is empty; it is the material the runtime loads")

    license_value = data.get("license")
    if license_value is not None and not isinstance(license_value, str):
        problems.append("`license` must be a string")

    compatibility = data.get("compatibility")
    if compatibility is not None and not isinstance(compatibility, (str, dict)):
        problems.append("`compatibility` must be a string or a mapping")

    metadata = data.get("metadata")
    if metadata is None:
        metadata = {}
    elif not isinstance(metadata, dict):
        problems.append("`metadata` must be a mapping of string to string")
        metadata = {}
    else:
        for key, value in metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                problems.append(
                    "`metadata.{}` must map a string to a string".format(key)
                )

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
        raise SkillError(path, problems)

    return Skill(
        name=name,
        description=description.strip(),
        body=content,
        source=path,
        directory=directory,
        extra_files=_supporting_files(directory),
        license=license_value,
        compatibility=compatibility,
        metadata=metadata,
        targets=targets,
        meta=meta,
    )


def _supporting_files(directory: Path) -> List[Path]:
    """Every file in the skill directory except SKILL.md, relative and sorted.

    The runtime gives a skill its directory as a private base, so references and
    scripts beside SKILL.md are part of the skill and have to travel with it.
    """
    found = [
        p.relative_to(directory)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != SKILL_FILENAME
    ]
    return found
