"""Registry of build targets.

To add a runtime: subclass Target, then add an instance to `_TARGETS`.
"""

from __future__ import annotations

from typing import Dict, List

from ..errors import TargetError
from .base import Target
from .opencode import OpencodeTarget

_TARGETS: Dict[str, Target] = {t.name: t for t in (OpencodeTarget(),)}


def all_targets() -> List[Target]:
    return [_TARGETS[name] for name in sorted(_TARGETS)]


def target_names() -> List[str]:
    return sorted(_TARGETS)


def get_target(name: str) -> Target:
    try:
        return _TARGETS[name]
    except KeyError:
        raise TargetError(
            "unknown target {!r}; known targets: {}".format(
                name, ", ".join(target_names())
            )
        )


__all__ = ["Target", "all_targets", "get_target", "target_names"]
