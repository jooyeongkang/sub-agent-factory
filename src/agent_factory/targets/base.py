"""The contract every emitter implements.

Adding support for another agent runtime means writing one subclass and
registering it -- nothing else in the codebase should need to change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..agent import Agent


class Target:
    """Turns canonical agents into the on-disk layout one runtime expects."""

    #: Name used on the command line (`--target <name>`).
    name = ""
    #: Human-readable one-liner shown by `agent-factory targets`.
    summary = ""
    #: Path inside the build output that mirrors the runtime's own layout.
    subdir = ""

    def output_path(self, agent: Agent) -> Path:
        """Where this agent lands, relative to the runtime's config root.

        The build directory mirrors the config root exactly, so installing is a
        plain copy of the tree with no path rewriting.
        """
        return Path(self.subdir) / "{}.md".format(agent.name)

    def render(self, agent: Agent) -> str:
        raise NotImplementedError

    def user_config_dir(self) -> Path:
        """The runtime's global config root for the current user."""
        raise NotImplementedError

    def project_config_dir(self, project_root: Path) -> Path:
        """The runtime's per-project config root inside `project_root`."""
        raise NotImplementedError


def render_markdown(frontmatter: Dict[str, Any], body: str) -> str:
    """Compose a frontmatter+body markdown file.

    Key order is whatever the caller inserted, so emitted files stay stable
    across builds and diff cleanly.
    """
    if frontmatter:
        dumped = yaml.safe_dump(
            frontmatter,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            # Long descriptions fold onto a second line at the default width;
            # still valid YAML, but it reads badly in a file humans open.
            width=4096,
        ).rstrip("\n")
        return "---\n{}\n---\n\n{}\n".format(dumped, body.strip())
    return "{}\n".format(body.strip())


def put(target: Dict[str, Any], key: str, value: Optional[Any]) -> None:
    """Set `key` only when `value` was actually specified.

    Emitting explicit nulls would override the runtime's own defaults, so
    unspecified canonical fields must stay absent from the output.
    """
    if value is None:
        return
    if isinstance(value, dict) and not value:
        return
    target[key] = value
