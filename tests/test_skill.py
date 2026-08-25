from __future__ import annotations

import pytest

from agent_factory.errors import SkillError
from agent_factory.skill import parse_skill

from .conftest import write_skill


def test_parses_minimal_skill(repo):
    path = write_skill(repo, "sample-skill", """\
        ---
        name: sample-skill
        description: A sample skill
        ---

        Reference material.
        """)
    skill = parse_skill(path)
    assert skill.name == "sample-skill"
    assert skill.description == "A sample skill"
    assert skill.body == "Reference material."
    assert skill.targets is None
    assert skill.extra_files == []
    assert skill.applies_to("opencode")


def test_full_frontmatter_round_trips(repo):
    path = write_skill(repo, "full-skill", """\
        ---
        name: full-skill
        description: Everything set
        license: MIT
        compatibility: opencode >= 1.18
        metadata:
          area: refactoring
        targets: [opencode]
        meta:
          tags: [python]
        ---

        Body.
        """)
    skill = parse_skill(path)
    assert skill.license == "MIT"
    assert skill.compatibility == "opencode >= 1.18"
    assert skill.metadata == {"area": "refactoring"}
    assert skill.targets == ["opencode"]
    assert skill.meta == {"tags": ["python"]}
    assert not skill.applies_to("other")


def test_name_must_match_directory(repo):
    path = write_skill(repo, "on-disk", """\
        ---
        name: in-frontmatter
        description: Mismatched
        ---

        Body.
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    # The directory is the only thing carrying identity, so this has to be loud.
    assert "they must match" in str(exc.value)


def test_unknown_field_is_rejected(repo):
    path = write_skill(repo, "typo", """\
        ---
        name: typo
        description: Has a typo
        descripton: oops
        ---

        Body.
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "unknown field `descripton`" in str(exc.value)


def test_description_must_be_one_line(repo):
    path = write_skill(repo, "multi", """\
        ---
        name: multi
        description: |
          first line
          second line
        ---

        Body.
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "single line" in str(exc.value)


def test_folded_description_is_accepted(repo):
    # A folded scalar is the normal way to wrap a long description in YAML and
    # produces a single-line string, so it must not trip the one-line check.
    path = write_skill(repo, "folded", """\
        ---
        name: folded
        description: >-
          a description long enough
          to wrap across lines
        ---

        Body.
        """)
    skill = parse_skill(path)
    assert skill.description == "a description long enough to wrap across lines"


def test_description_length_is_capped(repo):
    path = write_skill(repo, "long", """\
        ---
        name: long
        description: {}
        ---

        Body.
        """.format("x" * 1100))
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "at most 1024 characters" in str(exc.value)


def test_empty_body_is_rejected(repo):
    path = write_skill(repo, "hollow", """\
        ---
        name: hollow
        description: Nothing to load
        ---
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "body is empty" in str(exc.value)


def test_metadata_must_be_strings(repo):
    path = write_skill(repo, "meta-typed", """\
        ---
        name: meta-typed
        description: Bad metadata
        metadata:
          count: 3
        ---

        Body.
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "must map a string to a string" in str(exc.value)


def test_every_problem_is_reported_at_once(repo):
    path = write_skill(repo, "broken", """\
        ---
        name: mismatched
        nonsense: true
        ---
        """)
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    problems = exc.value.problems
    assert len(problems) == 4, problems


def test_missing_frontmatter(repo):
    path = write_skill(repo, "bare", "just prose\n")
    with pytest.raises(SkillError) as exc:
        parse_skill(path)
    assert "missing YAML frontmatter" in str(exc.value)


def test_supporting_files_are_found(repo):
    path = write_skill(repo, "with-refs", """\
        ---
        name: with-refs
        description: Has references
        ---

        Body.
        """)
    references = path.parent / "references"
    references.mkdir()
    (references / "notes.md").write_text("notes\n", encoding="utf-8")
    (path.parent / "check.py").write_text("print('hi')\n", encoding="utf-8")

    skill = parse_skill(path)
    assert [str(p) for p in skill.extra_files] == ["check.py", "references/notes.md"]
