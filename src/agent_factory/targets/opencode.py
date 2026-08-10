"""Emitter for opencode (https://opencode.ai).

opencode discovers agents by globbing `{agent,agents}/**/*.md` under its global
config dir (`~/.config/opencode`) and under `.opencode/` in a project, and takes
the agent's id from the filename. Because of that, `name` is *not* emitted --
the output filename carries it.

Verified against opencode 1.18.15 and its published config schema
(https://opencode.ai/config.json).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ..agent import Agent
from .base import Target, put, render_markdown


class OpencodeTarget(Target):
    name = "opencode"
    summary = "opencode agents (~/.config/opencode/agent, .opencode/agent)"
    subdir = "agent"

    def render(self, agent: Agent) -> str:
        frontmatter: Dict[str, Any] = {}
        # Ordered so the fields a human scans for come first.
        put(frontmatter, "description", agent.description)
        put(frontmatter, "mode", agent.mode)
        put(frontmatter, "model", agent.model)
        put(frontmatter, "variant", agent.variant)
        put(frontmatter, "temperature", agent.temperature)
        put(frontmatter, "top_p", agent.top_p)
        put(frontmatter, "steps", agent.steps)
        put(frontmatter, "color", agent.color)
        put(frontmatter, "hidden", agent.hidden)
        put(frontmatter, "disable", agent.disable)
        put(frontmatter, "permission", agent.permission)
        # Deprecated upstream in favour of `permission`, but still honoured.
        put(frontmatter, "tools", agent.tools)
        return render_markdown(frontmatter, agent.prompt)

    def user_config_dir(self) -> Path:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home) if config_home else Path.home() / ".config"
        return base / "opencode"

    def project_config_dir(self, project_root: Path) -> Path:
        return project_root / ".opencode"
