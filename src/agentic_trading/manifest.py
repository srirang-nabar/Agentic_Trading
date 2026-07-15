"""Artifact manifest hashing (Stage 0 helper, used through Stage 7).

Builds and verifies `results/MANIFEST.sha256`: SHA-256 hashes of all session
logs, configs, and derived tables, so volunteers can confirm the artifacts
they analyze are the artifacts that were produced.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file (streamed)."""
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build_manifest(root: Path, patterns: tuple[str, ...] = ("**/*",)) -> dict[str, str]:
    """Hash every file under `root` matching `patterns`.

    Returns {relative_posix_path: hex_digest}, sorted by path so the
    manifest is deterministic.
    """
    # Self-referential artifacts stay out of the manifest: the manifest
    # itself, and the fresh-machine transcript, which is mid-write while
    # the dry run's own Tier 2 verifies the manifest.
    excluded = {"MANIFEST.sha256", "fresh_machine_run.log"}
    entries: dict[str, str] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path.name not in excluded:
                entries[path.relative_to(root).as_posix()] = sha256_file(path)
    return dict(sorted(entries.items()))


def write_manifest(root: Path, manifest_path: Path | None = None) -> Path:
    """Write `MANIFEST.sha256` for `root` in `sha256sum -c` format."""
    manifest_path = manifest_path or root / "MANIFEST.sha256"
    lines = [f"{digest}  {rel}" for rel, digest in build_manifest(root).items()]
    manifest_path.write_text("\n".join(lines) + "\n")
    return manifest_path


def verify_manifest(root: Path, manifest_path: Path | None = None) -> list[str]:
    """Return a list of mismatched/missing paths (empty list = verified)."""
    manifest_path = manifest_path or root / "MANIFEST.sha256"
    failures: list[str] = []
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        path = root / rel
        if not path.is_file():
            failures.append(f"missing: {rel}")
        elif sha256_file(path) != digest:
            failures.append(f"hash mismatch: {rel}")
    return failures
