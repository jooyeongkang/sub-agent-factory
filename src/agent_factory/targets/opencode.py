"""Emitter for opencode (https://opencode.ai).

opencode discovers agents by globbing `{agent,agents}/**/*.md` under its global
config dir (`~/.config/opencode`) and under `.opencode/` in a project, and takes
the agent's id from the filename. Because of that, `name` is *not* emitted --
the output filename carries it.

Skills work the other way round: they live at `skills/<name>/SKILL.md` under the
same config root, every file is called `SKILL.md`, and the runtime checks that
the frontmatter `name` matches the directory. So `render_skill` *does* emit
`name`, and must.

Verified against opencode 1.18.15 and its published config schema
(https://opencode.ai/config.json).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ..agent import Agent
from ..skill import Skill
from .base import Target, put, render_markdown


class OpencodeTarget(Target):
    name = "opencode"
    summary = "opencode agents and skills (~/.config/opencode, .opencode)"
    subdir = "agent"
    skills_subdir = "skills"

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

    def render_skill(self, skill: Skill) -> str:
        frontmatter: Dict[str, Any] = {}
        # Unlike an agent, `name` is required here: the runtime validates it
        # against the containing directory rather than inferring it.
        put(frontmatter, "name", skill.name)
        put(frontmatter, "description", skill.description)
        put(frontmatter, "license", skill.license)
        put(frontmatter, "compatibility", skill.compatibility)
        put(frontmatter, "metadata", skill.metadata)
        return render_markdown(frontmatter, skill.body)

    def user_config_dir(self) -> Path:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home) if config_home else Path.home() / ".config"
        return base / "opencode"

    def project_config_dir(self, project_root: Path) -> Path:
        return project_root / ".opencode"
