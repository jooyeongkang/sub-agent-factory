from __future__ import annotations

import json

import yaml

from agent_factory.agent import split_frontmatter
from agent_factory.builder import build_target, install_target
from agent_factory.loader import load_agents
from agent_factory.targets import get_target

from .conftest import VALID, write_agent


def build(repo, tmp_path):
    agents = load_agents(repo)
    return build_target(agents, get_target("opencode"), tmp_path / "dist")


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
