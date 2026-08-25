"""Compiling agents and skills into per-target output, and installing that output."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from .agent import Agent
from .skill import Skill
from .targets import Target

#: Dropped into every install directory so a later install knows exactly which
#: files it owns and may remove. Without it, pruning would have to guess.
INSTALL_MANIFEST = ".agent-factory.json"


@dataclass
class BuildResult:
    target: Target
    out_dir: Path
    files: List[Path]  # absolute paths of written agent files
    skipped: List[Agent]  # agents this target opted out of
    skill_files: List[Path] = field(default_factory=list)
    skipped_skills: List[Skill] = field(default_factory=list)

    @property
    def all_files(self) -> List[Path]:
        """Everything written for this target, which is what install acts on."""
        return list(self.files) + list(self.skill_files)


def build_target(
    agents: Sequence[Agent],
    target: Target,
    out_root: Path,
    clean: bool = True,
    skills: Sequence[Skill] = (),
) -> BuildResult:
    """Render every applicable agent and skill for one target under `out_root/<target>/`."""
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

    skill_files: List[Path] = []
    skipped_skills: List[Skill] = []
    for skill in skills:
        if not target.supports_skills or not skill.applies_to(target.name):
            skipped_skills.append(skill)
            continue
        destination = out_dir / target.skill_output_path(skill)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(target.render_skill(skill), encoding="utf-8")
        skill_files.append(destination)
        # The runtime treats the skill's directory as its private base, so
        # references and scripts beside SKILL.md have to travel with it.
        for relative in skill.extra_files:
            copied = destination.parent / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(skill.directory / relative, copied)
            skill_files.append(copied)

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
        "skills": [
            {
                "name": s.name,
                "source": str(s.source),
                "output": str(
                    (out_dir / target.skill_output_path(s)).relative_to(out_dir)
                ),
            }
            for s in skills
            if target.supports_skills and s.applies_to(target.name)
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return BuildResult(
        target=target,
        out_dir=out_dir,
        files=written,
        skipped=skipped,
        skill_files=skill_files,
        skipped_skills=skipped_skills,
    )


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
    so deleting an agent or skill from the repo actually retires it from the
    runtime. Files in `dest` that the factory never installed are left untouched.
    """
    relative = sorted(str(f.relative_to(result.out_dir)) for f in result.all_files)
    previous = _read_install_manifest(dest)
    stale = [name for name in previous if name not in relative]

    if dry_run:
        return InstallResult(dest=dest, installed=relative, pruned=stale, linked=link)

    for name in stale:
        target_path = dest / name
        if target_path.is_file() or target_path.is_symlink():
            target_path.unlink()
        # A retired skill would otherwise leave its now-empty directory behind,
        # which the runtime still lists as a broken skill.
        _prune_empty_parents(dest, target_path.parent)

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


def _prune_empty_parents(root: Path, directory: Path) -> None:
    """Remove directories left empty by pruning, stopping at the install root."""
    root = root.resolve()
    current = directory.resolve()
    while current != root and root in current.parents:
        if not current.is_dir() or any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


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
