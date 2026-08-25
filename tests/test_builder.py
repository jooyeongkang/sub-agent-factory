from __future__ import annotations

import json

import yaml

from agent_factory.agent import split_frontmatter
from agent_factory.builder import build_target, install_target
from agent_factory.loader import load_agents, load_skills
from agent_factory.targets import get_target

from .conftest import SKILL, VALID, write_agent, write_skill


def build(repo, tmp_path):
    agents = load_agents(repo)
    skills = load_skills(repo)
    return build_target(agents, get_target("opencode"), tmp_path / "dist", skills=skills)


def test_opencode_output_drops_name_and_meta(repo, tmp_path):
    write_agent(repo, "sample", """\
        ---
        name: sample
        description: A sample agent
        mode: subagent
        temperature: 0.2
        permission:
          edit: deny
        targets: [opencode]
        meta:
          tags: [x]
        ---

        Prompt body.
        """)
    result = build(repo, tmp_path)
    out = result.out_dir / "agent" / "sample.md"
    raw, body = split_frontmatter(out.read_text(encoding="utf-8"))
    data = yaml.safe_load(raw)

    # opencode takes the id from the filename; repo bookkeeping never ships.
    assert "name" not in data
    assert "meta" not in data
    assert "targets" not in data
    assert data["description"] == "A sample agent"
    assert data["permission"] == {"edit": "deny"}
    assert body.strip() == "Prompt body."


def test_unset_fields_are_omitted(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    result = build(repo, tmp_path)
    data = yaml.safe_load(
        split_frontmatter((result.out_dir / "agent" / "sample.md").read_text())[0]
    )
    assert set(data) == {"description", "mode"}


def test_targets_filter_skips_agent(repo, tmp_path):
    write_agent(repo, "sample", VALID.replace(
        "mode: subagent", "mode: subagent\ntargets: [somewhere-else]"
    ))
    result = build(repo, tmp_path)
    assert result.files == []
    assert [a.name for a in result.skipped] == ["sample"]


def test_build_manifest_lists_sources(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    result = build(repo, tmp_path)
    manifest = json.loads((result.out_dir / "build-manifest.json").read_text())
    assert manifest["target"] == "opencode"
    assert manifest["agents"][0]["name"] == "sample"


def test_build_cleans_stale_output(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    result = build(repo, tmp_path)
    stale = result.out_dir / "agent" / "gone.md"
    stale.write_text("stale", encoding="utf-8")

    build(repo, tmp_path)
    assert not stale.exists()


def test_install_mirrors_runtime_layout(repo, tmp_path):
    """The install root is the runtime's config root, so `agent/` comes along."""
    write_agent(repo, "sample", VALID)
    dest = tmp_path / "config"
    install_target(build(repo, tmp_path), dest)
    assert (dest / "agent" / "sample.md").is_file()


def test_install_copies_and_prunes(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_agent(repo, "second", VALID.replace("sample", "second"))
    dest = tmp_path / "config"

    install_target(build(repo, tmp_path), dest)
    assert (dest / "agent" / "sample.md").is_file()
    assert (dest / "agent" / "second.md").is_file()

    # A file the factory never installed must survive the prune.
    foreign = dest / "agent" / "hand-written.md"
    foreign.write_text("mine", encoding="utf-8")

    (repo / "agents" / "second.md").unlink()
    result = install_target(build(repo, tmp_path), dest)

    assert result.pruned == ["agent/second.md"]
    assert not (dest / "agent" / "second.md").exists()
    assert foreign.read_text() == "mine"


def test_install_link_creates_symlinks(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    dest = tmp_path / "config"
    install_target(build(repo, tmp_path), dest, link=True)
    assert (dest / "agent" / "sample.md").is_symlink()


def test_install_dry_run_writes_nothing(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    dest = tmp_path / "config"
    result = install_target(build(repo, tmp_path), dest, dry_run=True)
    assert result.installed == ["agent/sample.md"]
    assert not dest.exists()


def test_skill_lands_in_its_own_directory(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", SKILL)

    result = build(repo, tmp_path)
    output = result.out_dir / "skills" / "sample-skill" / "SKILL.md"
    assert output.is_file()
    assert result.skill_files == [output]


def test_skill_output_keeps_name_and_drops_meta(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", """\
        ---
        name: sample-skill
        description: A sample skill
        meta:
          tags: [python]
        ---

        Sample material.
        """)

    result = build(repo, tmp_path)
    text = (result.out_dir / "skills" / "sample-skill" / "SKILL.md").read_text()
    front, body = split_frontmatter(text)
    data = yaml.safe_load(front)
    # Unlike an agent, the runtime validates `name` against the directory, so it
    # has to be emitted rather than left implicit in the filename.
    assert data["name"] == "sample-skill"
    assert data["description"] == "A sample skill"
    assert "meta" not in data
    assert body.strip() == "Sample material."


def test_optional_skill_fields_are_absent_when_unset(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", SKILL)

    result = build(repo, tmp_path)
    text = (result.out_dir / "skills" / "sample-skill" / "SKILL.md").read_text()
    data = yaml.safe_load(split_frontmatter(text)[0])
    assert set(data) == {"name", "description"}


def test_supporting_files_are_copied(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    path = write_skill(repo, "sample-skill", SKILL)
    references = path.parent / "references"
    references.mkdir()
    (references / "notes.md").write_text("notes\n", encoding="utf-8")

    result = build(repo, tmp_path)
    copied = result.out_dir / "skills" / "sample-skill" / "references" / "notes.md"
    assert copied.read_text() == "notes\n"
    assert copied in result.skill_files


def test_targets_filter_applies_to_skills(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "elsewhere", """\
        ---
        name: elsewhere
        description: Not for opencode
        targets: [other]
        ---

        Body.
        """)

    result = build(repo, tmp_path)
    assert result.skill_files == []
    assert [s.name for s in result.skipped_skills] == ["elsewhere"]
    assert not (result.out_dir / "skills").exists()


def test_manifest_records_skills(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", SKILL)

    result = build(repo, tmp_path)
    manifest = json.loads((result.out_dir / "build-manifest.json").read_text())
    assert manifest["skills"] == [
        {
            "name": "sample-skill",
            "source": str(repo / "skills" / "sample-skill" / "SKILL.md"),
            "output": "skills/sample-skill/SKILL.md",
        }
    ]


def test_install_places_skills(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", SKILL)
    dest = tmp_path / "config"

    install_target(build(repo, tmp_path), dest)
    assert (dest / "agent" / "sample.md").is_file()
    assert (dest / "skills" / "sample-skill" / "SKILL.md").is_file()


def test_retired_skill_leaves_no_empty_directory(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    skill_path = write_skill(repo, "sample-skill", SKILL)
    dest = tmp_path / "config"
    install_target(build(repo, tmp_path), dest)

    skill_path.unlink()
    result = install_target(build(repo, tmp_path), dest)

    assert "skills/sample-skill/SKILL.md" in result.pruned
    # An orphaned directory would still be listed by the runtime as a skill.
    assert not (dest / "skills" / "sample-skill").exists()


def test_install_leaves_unrelated_files_alone(repo, tmp_path):
    write_agent(repo, "sample", VALID)
    write_skill(repo, "sample-skill", SKILL)
    dest = tmp_path / "config"
    handwritten = dest / "skills" / "by-hand"
    handwritten.mkdir(parents=True)
    (handwritten / "SKILL.md").write_text("mine\n", encoding="utf-8")

    install_target(build(repo, tmp_path), dest)
    install_target(build(repo, tmp_path), dest)
    assert (handwritten / "SKILL.md").read_text() == "mine\n"
