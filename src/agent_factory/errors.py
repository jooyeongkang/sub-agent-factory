"""Error types carrying enough context to point at the offending file."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence


class FactoryError(Exception):
    """Base class for every error this package raises deliberately."""


class FileError(FactoryError):
    """One source file failed validation, with every problem found in it.

    Validation collects problems rather than raising at the first one, so a
    batch of files can be fixed in a single pass.
    """

    def __init__(self, path: Path, problems: Sequence[str]) -> None:
        self.path = path
        self.problems: List[str] = list(problems)
        joined = "\n".join("  - " + p for p in self.problems)
        super().__init__("{}:\n{}".format(path, joined))


class AgentError(FileError):
    """One agent file failed validation."""


class SkillError(FileError):
    """One SKILL.md failed validation."""


class LoadError(FactoryError):
    """One or more source files failed to load."""

    def __init__(self, errors: Sequence[FileError], extra: Sequence[str] = ()) -> None:
        self.errors: List[FileError] = list(errors)
        self.extra: List[str] = list(extra)
        blocks = [str(e) for e in self.errors] + list(self.extra)
        super().__init__("\n".join(blocks))


class TargetError(FactoryError):
    """An unknown or unusable build target was requested."""
