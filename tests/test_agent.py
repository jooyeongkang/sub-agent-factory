from __future__ import annotations

import pytest

from agent_factory.agent import parse_agent, split_frontmatter
from agent_factory.errors import AgentError

from .conftest import write_agent


def test_parses_minimal_agent(repo):
    path = write_agent(repo, "sample", """\
        ---
        name: sample
        description: A sample agent
        ---

        Body text.
        """)
    agent = parse_agent(path)
    assert agent.name == "sample"
    assert agent.description == "A sample agent"
    assert agent.prompt == "Body text."
    assert agent.mode == "subagent"
    assert agent.targets is None
    assert agent.applies_to("opencode")


def test_full_frontmatter_round_trips(repo):
    path = write_agent(repo, "full", """\
        ---
        name: full
        description: Everything set
        mode: all
        model: anthropic/claude-sonnet-4-5
        temperature: 0.5
        top_p: 0.9
        steps: 20
        color: "#FF5733"
        hidden: true
        disable: false
        permission:
          edit: deny
          bash:
            "git *": allow
        targets: [opencode]
        meta:
          tags: [a, b]
        ---

        Prompt.
        """)
    agent = parse_agent(path)
    assert agent.mode == "all"
    assert agent.model == "anthropic/claude-sonnet-4-5"
    assert agent.temperature == 0.5
    assert agent.steps == 20
    assert agent.permission["bash"]["git *"] == "allow"
    assert agent.meta["tags"] == ["a", "b"]
    assert agent.applies_to("opencode")
    assert not agent.applies_to("other")


def test_split_frontmatter_without_block():
    raw, body = split_frontmatter("no frontmatter here")
    assert raw == ""
    assert body == "no frontmatter here"


def test_missing_frontmatter_is_an_error(repo):
    path = write_agent(repo, "bare", "just a body\n")
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert "missing YAML frontmatter" in str(exc.value)


def test_name_must_match_filename(repo):
    path = write_agent(repo, "actual", """\
        ---
        name: declared
        description: Mismatched
        ---

        Body.
        """)
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert "must match" in str(exc.value)


def test_unknown_field_is_rejected(repo):
    path = write_agent(repo, "typo", """\
        ---
        name: typo
        description: Has a typo
        modle: subagent
        ---

        Body.
        """)
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert "unknown field `modle`" in str(exc.value)


def test_all_problems_reported_together(repo):
    path = write_agent(repo, "messy", """\
        ---
        name: messy
        description: Bad values
        mode: nonsense
        temperature: 4
        model: notprovidermodel
        ---

        Body.
        """)
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert len(exc.value.problems) == 3


def test_empty_body_is_an_error(repo):
    path = write_agent(repo, "empty", """\
        ---
        name: empty
        description: No prompt
        ---
        """)
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert "body is empty" in str(exc.value)


def test_bad_permission_verdict_is_rejected(repo):
    path = write_agent(repo, "perm", """\
        ---
        name: perm
        description: Bad verdict
        permission:
          edit: maybe
        ---

        Body.
        """)
    with pytest.raises(AgentError) as exc:
        parse_agent(path)
    assert "permission.edit" in str(exc.value)


def test_deprecated_tools_field_warns_but_parses(repo):
    path = write_agent(repo, "legacy", """\
        ---
        name: legacy
        description: Uses deprecated tools
        tools:
          write: false
        ---

        Body.
        """)
    agent = parse_agent(path)
    assert agent.tools == {"write": False}
    assert any("deprecated" in w for w in agent.warnings)
