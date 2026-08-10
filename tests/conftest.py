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
