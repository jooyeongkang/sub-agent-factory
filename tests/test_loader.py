from __future__ import annotations

import pytest

from agent_factory.errors import FactoryError, LoadError
from agent_factory.loader import find_root, load_agents, load_skills, skill_paths

from .conftest import SKILL, VALID, write_agent, write_skill


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


def test_loads_skills(repo):
    write_skill(repo, "one-skill", SKILL.replace("sample-skill", "one-skill"))
    write_skill(repo, "two-skill", SKILL.replace("sample-skill", "two-skill"))

    skills = load_skills(repo)
    assert sorted(s.name for s in skills) == ["one-skill", "two-skill"]


def test_no_skills_directory_is_fine(repo):
    assert load_skills(repo) == []


def test_nested_skill_directories_are_not_discovered(repo):
    # The directory name is the identity, so `skills/a/b/SKILL.md` would be
    # ambiguous; only the top level counts.
    nested = repo / "skills" / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(SKILL, encoding="utf-8")

    assert skill_paths(repo) == []


def test_duplicate_skill_names_are_fatal(repo):
    # Two directories cannot collide by name, so the duplicate has to come from
    # frontmatter that disagrees with its directory -- caught per-file first.
    write_skill(repo, "dup", SKILL.replace("sample-skill", "dup"))
    write_skill(repo, "other", SKILL.replace("sample-skill", "dup"))

    with pytest.raises(LoadError) as exc:
        load_skills(repo)
    assert "they must match" in str(exc.value)


def test_broken_skills_are_all_reported(repo):
    write_skill(repo, "bad-one", "no frontmatter\n")
    write_skill(repo, "bad-two", "also none\n")

    with pytest.raises(LoadError) as exc:
        load_skills(repo)
    assert len(exc.value.errors) == 2
