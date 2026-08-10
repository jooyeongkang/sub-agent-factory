"""Command line entry point: `agent-factory`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from .agent import Agent
from .builder import build_target, install_target
from .errors import FactoryError
from .loader import find_root, load_agents
from .targets import Target, all_targets, get_target, target_names


def _resolve_targets(names: Optional[Sequence[str]]) -> List[Target]:
    if not names:
        return all_targets()
    return [get_target(n) for n in names]


def _load(root_arg: Optional[str]) -> "tuple[Path, List[Agent]]":
    root = Path(root_arg).resolve() if root_arg else find_root()
    agents = load_agents(root)
    for agent in agents:
        for warning in agent.warnings:
            print("warning: {}: {}".format(agent.source, warning), file=sys.stderr)
    return root, agents


def cmd_targets(args: argparse.Namespace) -> int:
    for target in all_targets():
        print("{:12} {}".format(target.name, target.summary))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root, agents = _load(args.root)
    print("ok: {} agent(s) valid in {}".format(len(agents), root / "agents"))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    _, agents = _load(args.root)
    if args.target:
        agents = [a for a in agents if a.applies_to(args.target)]

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": a.name,
                        "description": a.description,
                        "mode": a.mode,
                        "model": a.model,
                        "targets": a.targets,
                        "tags": a.meta.get("tags", []),
                        "source": str(a.source),
                    }
                    for a in agents
                ],
                indent=2,
            )
        )
        return 0

    if not agents:
        print("no agents found")
        return 0
    width = max(len(a.name) for a in agents)
    for agent in agents:
        print("{:{w}}  {}".format(agent.name, agent.description, w=width))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    root, agents = _load(args.root)
    out_root = Path(args.out).resolve() if args.out else root / "dist"
    for target in _resolve_targets(args.target):
        result = build_target(agents, target, out_root, clean=not args.no_clean)
        note = ""
        if result.skipped:
            note = " ({} skipped by `targets:`)".format(len(result.skipped))
        print(
            "built {} agent(s) for {} -> {}{}".format(
                len(result.files), target.name, result.out_dir, note
            )
        )
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    root, agents = _load(args.root)
    out_root = Path(args.out).resolve() if args.out else root / "dist"

    for target in _resolve_targets(args.target):
        result = build_target(agents, target, out_root, clean=True)
        if args.dest:
            dest = Path(args.dest).resolve()
        elif args.scope == "project":
            dest = target.project_config_dir(Path(args.project_dir).resolve())
        else:
            dest = target.user_config_dir()

        installed = install_target(
            result, dest, link=args.link, dry_run=args.dry_run
        )
        verb = "would install" if args.dry_run else (
            "linked" if args.link else "installed"
        )
        print(
            "{} {} agent(s) for {} -> {}".format(
                verb, len(installed.installed), target.name, installed.dest
            )
        )
        for name in installed.pruned:
            print(
                "  {} stale {}".format(
                    "would remove" if args.dry_run else "removed", name
                )
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-factory",
        description="Compile canonical sub-agent definitions for agent runtimes.",
    )
    parser.add_argument(
        "--root",
        help="repo root (default: nearest parent containing agents/)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("targets", help="list supported runtimes")
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("validate", help="check every agent against the schema")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("list", help="list agents")
    p.add_argument("--target", choices=target_names(), help="only agents for this target")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("build", help="render agents into dist/")
    p.add_argument("--target", action="append", choices=target_names(),
                   help="build only this target (repeatable)")
    p.add_argument("--out", help="output root (default: <root>/dist)")
    p.add_argument("--no-clean", action="store_true",
                   help="keep existing files in the output directory")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("install", help="build, then place agents where the runtime finds them")
    p.add_argument("--target", action="append", choices=target_names(),
                   help="install only this target (repeatable)")
    p.add_argument("--scope", choices=("user", "project"), default="user",
                   help="install globally for the user, or into a project (default: user)")
    p.add_argument("--project-dir", default=".",
                   help="project root when --scope project (default: cwd)")
    p.add_argument("--dest",
                   help="explicit config root to install into, overriding --scope")
    p.add_argument("--out", help="build output root (default: <root>/dist)")
    p.add_argument("--link", action="store_true",
                   help="symlink built files instead of copying")
    p.add_argument("--dry-run", action="store_true", help="report without writing")
    p.set_defaults(func=cmd_install)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FactoryError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
