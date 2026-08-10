"""Discovery of canonical agent files and location of the repo root."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .agent import Agent, parse_agent
from .errors import AgentError, FactoryError, LoadError

AGENTS_DIRNAME = "agents"


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


def load_agents(root: Path) -> List[Agent]:
    """Parse every agent under `root`, raising LoadError with all failures at once."""
    agents: List[Agent] = []
    errors: List[AgentError] = []
    for path in agent_paths(root):
        try:
            agents.append(parse_agent(path))
        except AgentError as exc:
            errors.append(exc)

    extra: List[str] = []
    seen: Dict[str, Path] = {}
    for agent in agents:
        previous = seen.get(agent.name)
        if previous is not None:
            # Two files claiming one name would race to overwrite each other in
            # the install dir, so this has to be fatal rather than a warning.
            extra.append(
                "duplicate agent name {!r}: {} and {}".format(
                    agent.name, previous, agent.source
                )
            )
        else:
            seen[agent.name] = agent.source

    if errors or extra:
        raise LoadError(errors, extra)
    return agents
