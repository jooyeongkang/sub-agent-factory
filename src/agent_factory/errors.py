"""Error types carrying enough context to point at the offending file."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence


class FactoryError(Exception):
    """Base class for every error this package raises deliberately."""


class AgentError(FactoryError):
    """One agent file failed validation, with every problem found in it."""

    def __init__(self, path: Path, problems: Sequence[str]) -> None:
        self.path = path
        self.problems: List[str] = list(problems)
        joined = "\n".join("  - " + p for p in self.problems)
        super().__init__("{}:\n{}".format(path, joined))


class LoadError(FactoryError):
    """One or more agent files failed to load."""

    def __init__(self, errors: Sequence[AgentError], extra: Sequence[str] = ()) -> None:
        self.errors: List[AgentError] = list(errors)
        self.extra: List[str] = list(extra)
        blocks = [str(e) for e in self.errors] + list(self.extra)
        super().__init__("\n".join(blocks))


class TargetError(FactoryError):
    """An unknown or unusable build target was requested."""
