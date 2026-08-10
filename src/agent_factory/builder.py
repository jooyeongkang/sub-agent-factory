"""Compiling agents into per-target output, and installing that output."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from .agent import Agent
from .targets import Target

#: Dropped into every install directory so a later install knows exactly which
#: files it owns and may remove. Without it, pruning would have to guess.
INSTALL_MANIFEST = ".agent-factory.json"


@dataclass
class BuildResult:
    target: Target
    out_dir: Path
    files: List[Path]  # absolute paths of written files
    skipped: List[Agent]  # agents this target opted out of


def build_target(
    agents: Sequence[Agent], target: Target, out_root: Path, clean: bool = True
) -> BuildResult:
    """Render every applicable agent for one target under `out_root/<target>/`."""
    out_dir = out_root / target.name
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    written: List[Path] = []
    skipped: List[Agent] = []
    for agent in agents:
        if not agent.applies_to(target.name):
            skipped.append(agent)
            continue
        destination = out_dir / target.output_path(agent)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(target.render(agent), encoding="utf-8")
        written.append(destination)

    manifest = {
        "target": target.name,
        "agents": [
            {
                "name": a.name,
                "source": str(a.source),
                "output": str((out_dir / target.output_path(a)).relative_to(out_dir)),
            }
            for a in agents
            if a.applies_to(target.name)
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return BuildResult(target=target, out_dir=out_dir, files=written, skipped=skipped)


@dataclass
class InstallResult:
    dest: Path
    installed: List[str]
    pruned: List[str]
    linked: bool


def install_target(
    result: BuildResult, dest: Path, link: bool = False, dry_run: bool = False
) -> InstallResult:
    """Place a target's built files into `dest`.

    Files this factory installed previously but no longer produces are removed,
    so deleting an agent from the repo actually retires it from the runtime.
    Files in `dest` that the factory never installed are left untouched.
    """
    relative = sorted(str(f.relative_to(result.out_dir)) for f in result.files)
    previous = _read_install_manifest(dest)
    stale = [name for name in previous if name not in relative]

    if dry_run:
        return InstallResult(dest=dest, installed=relative, pruned=stale, linked=link)

    for name in stale:
        target_path = dest / name
        if target_path.is_file() or target_path.is_symlink():
            target_path.unlink()

    for name in relative:
        source = result.out_dir / name
        destination = dest / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() or destination.is_symlink():
            destination.unlink()
        if link:
            # Relative symlinks would break once dest and repo diverge, so the
            # link points at the absolute built file.
            os.symlink(source.resolve(), destination)
        else:
            shutil.copyfile(source, destination)

    _write_install_manifest(dest, result.target.name, relative, link)
    return InstallResult(dest=dest, installed=relative, pruned=stale, linked=link)


def _read_install_manifest(dest: Path) -> List[str]:
    path = dest / INSTALL_MANIFEST
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # A corrupt manifest must not block an install; it only costs us the
        # ability to prune this once.
        return []
    files = data.get("files", [])
    return [f for f in files if isinstance(f, str)]


def _write_install_manifest(
    dest: Path, target_name: str, files: List[str], linked: bool
) -> None:
    payload: Dict[str, object] = {
        "target": target_name,
        "linked": linked,
        "files": files,
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / INSTALL_MANIFEST).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
