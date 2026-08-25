"""Discovery of canonical agent and skill files, and location of the repo root."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .agent import Agent, parse_agent
from .errors import AgentError, FactoryError, FileError, LoadError, SkillError
from .skill import SKILL_FILENAME, Skill, parse_skill

AGENTS_DIRNAME = "agents"
SKILLS_DIRNAME = "skills"


def find_root(start: Optional[Path] = None) -> Path:
    """Walk up from `start` looking for the repo root (the dir holding `agents/`)."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / AGENTS_DIRNAME).is_dir():
            return candidate
    raise FactoryError(
        "no `{}/` directory found in {} or any parent".format(AGENTS_DIRNAME, current)
    )


def agent_paths(root: Path) -> List[Path]:
    """Every canonical agent file, sorted for deterministic builds.

    Nested directories are supported and used purely for humans to organise by
    topic: the agent's identity comes from its filename, never its folder.
    """
    return sorted((root / AGENTS_DIRNAME).rglob("*.md"))


def skill_paths(root: Path) -> List[Path]:
    """Every canonical `SKILL.md`, sorted for deterministic builds.

    One directory per skill, and the directory name is the skill's identity, so
    unlike agents these are deliberately not searched recursively -- a nested
    `skills/a/b/SKILL.md` would have an ambiguous name.
    """
    skills_dir = root / SKILLS_DIRNAME
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/{}".format(SKILL_FILENAME)))


def load_agents(root: Path) -> List[Agent]:
    """Parse every agent under `root`, raising LoadError with all failures at once."""
    agents: List[Agent] = []
    errors: List[FileError] = []
    for path in agent_paths(root):
        try:
            agents.append(parse_agent(path))
        except AgentError as exc:
            errors.append(exc)

    extra = _duplicate_problems("agent", [(a.name, a.source) for a in agents])
    if errors or extra:
        raise LoadError(errors, extra)
    return agents


def load_skills(root: Path) -> List[Skill]:
    """Parse every skill under `root`, raising LoadError with all failures at once.

    A repo with no `skills/` directory is fine and yields none; skills are an
    optional addition to a library of agents.
    """
    skills: List[Skill] = []
    errors: List[FileError] = []
    for path in skill_paths(root):
        try:
            skills.append(parse_skill(path))
        except SkillError as exc:
            errors.append(exc)

    extra = _duplicate_problems("skill", [(s.name, s.source) for s in skills])
    if errors or extra:
        raise LoadError(errors, extra)
    return skills


def _duplicate_problems(
    kind: str, named: Sequence["tuple[str, Path]"]
) -> List[str]:
    """Report any name claimed by two source files.

    Two files claiming one name would race to overwrite each other in the
    install directory, so this has to be fatal rather than a warning.
    """
    problems: List[str] = []
    seen: Dict[str, Path] = {}
    for name, source in named:
        previous = seen.get(name)
        if previous is not None:
            problems.append(
                "duplicate {} name {!r}: {} and {}".format(kind, name, previous, source)
            )
        else:
            seen[name] = source
    return problems
