from __future__ import annotations

import pytest

from agent_factory.errors import FactoryError, LoadError
from agent_factory.loader import find_root, load_agents

from .conftest import VALID, write_agent


def test_loads_nested_agents(repo):
    write_agent(repo, "one", VALID.replace("sample", "one"))
    nested = repo / "agents" / "topic"
    nested.mkdir()
    (nested / "two.md").write_text(VALID.replace("sample", "two"), encoding="utf-8")

    agents = load_agents(repo)
    assert sorted(a.name for a in agents) == ["one", "two"]


def test_duplicate_names_are_fatal(repo):
    write_agent(repo, "dup", VALID.replace("sample", "dup"))
    nested = repo / "agents" / "elsewhere"
    nested.mkdir()
    (nested / "dup.md").write_text(VALID.replace("sample", "dup"), encoding="utf-8")

    with pytest.raises(LoadError) as exc:
        load_agents(repo)
    assert "duplicate agent name" in str(exc.value)


def test_every_broken_file_is_reported(repo):
    write_agent(repo, "bad-one", "no frontmatter\n")
    write_agent(repo, "bad-two", "also none\n")

    with pytest.raises(LoadError) as exc:
        load_agents(repo)
    assert len(exc.value.errors) == 2


def test_find_root_walks_up(repo):
    nested = repo / "agents" / "deep"
    nested.mkdir()
    assert find_root(nested) == repo.resolve()


def test_find_root_without_agents_dir(tmp_path):
    with pytest.raises(FactoryError):
        find_root(tmp_path)
