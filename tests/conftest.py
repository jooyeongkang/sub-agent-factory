from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

VALID = """\
---
name: sample
description: A sample agent
mode: subagent
---

Do the sample thing.
"""


SKILL = """\
---
name: sample-skill
description: A sample skill
---

Sample material.
"""


def write_agent(root: Path, name: str, content: str) -> Path:
    agents = root / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    path = agents / "{}.md".format(name)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path


def write_skill(root: Path, name: str, content: str) -> Path:
    """Write `skills/<name>/SKILL.md`; the directory name is the skill's identity."""
    directory = root / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path
