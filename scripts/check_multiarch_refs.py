#!/usr/bin/env python3
"""Verify that multi-arch element source refs are updated symmetrically.

When an element has architecture-conditional sources (e.g., x86_64 and aarch64),
a version bump or source ref update must update the refs for all architectures,
not leave one stale.

Usage:
    # Check working tree against BASE_SHA (e.g. in PR CI or refresh workflow):
    python3 scripts/check_multiarch_refs.py --base <base-sha>

    # Check commits between BASE and HEAD:
    python3 scripts/check_multiarch_refs.py --base <base-sha> --head HEAD

    # Check specific files against a base revision:
    python3 scripts/check_multiarch_refs.py --base <base-sha> elements/lab-runner/kubectl.bst
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


def extract_arch_refs(content: str) -> dict[str, str]:
    """Extract architecture-specific refs from conditional sources.

    Matches BuildStream (?) blocks with arch == "<arch>" and ref: <digest>.
    Returns a dict mapping arch name ('x86_64', 'aarch64') to its ref string.
    """
    arch_refs: dict[str, str] = {}
    current_arch: str | None = None
    in_conditional = False

    for line in content.splitlines():
        if "(?):" in line:
            in_conditional = True
            current_arch = None
            continue

        if in_conditional:
            arch_match = re.search(r'arch\s*==\s*["\'](x86_64|aarch64)["\']', line)
            if arch_match:
                current_arch = arch_match.group(1)
                continue

            # Top-level key out of conditional block
            if re.match(r"^[a-z_-]+:", line):
                in_conditional = False
                current_arch = None
                continue

            if current_arch:
                ref_match = re.search(r"^\s*ref:\s*([0-9a-fA-F]{40,64})\b", line)
                if ref_match:
                    arch_refs[current_arch] = ref_match.group(1)
                    current_arch = None

    return arch_refs


def check_parity(
    file_path: str,
    base_content: str,
    head_content: str,
) -> str | None:
    """Check whether multi-arch refs in file_path were updated symmetrically.

    Returns an error message string if asymmetric, or None if symmetric / not applicable.
    """
    base_refs = extract_arch_refs(base_content)
    head_refs = extract_arch_refs(head_content)

    # Enforce parity on any element defining both x86_64 and aarch64 conditional refs.
    if "x86_64" in base_refs and "aarch64" in base_refs:
        x86_changed = base_refs.get("x86_64") != head_refs.get("x86_64")
        arm_changed = base_refs.get("aarch64") != head_refs.get("aarch64")

        if x86_changed != arm_changed:
            return (
                f"{file_path}: asymmetric multi-arch ref update "
                f"(x86_64 changed={x86_changed}, aarch64 changed={arm_changed}). "
                f"Both architecture refs must be updated together."
            )

    return None


def get_git_file_content(rev: str, file_path: str) -> str | None:
    """Retrieve file content from git at a given revision."""
    try:
        return subprocess.check_output(
            ["git", "show", f"{rev}:{file_path}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def get_changed_files(base_rev: str, head_rev: str | None) -> list[str]:
    """List .bst files changed between base_rev and head_rev (or working tree)."""
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
    if head_rev:
        cmd.append(f"{base_rev}...{head_rev}")
    else:
        cmd.append(base_rev)
    cmd.extend(["--", "elements/*.bst", "elements/**/*.bst"])

    try:
        output = subprocess.check_output(cmd, text=True)
        return [line.strip() for line in output.splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        cmd_direct = ["git", "diff", "--name-only", "--diff-filter=ACMR", base_rev]
        if head_rev:
            cmd_direct.append(head_rev)
        cmd_direct.extend(["--", "elements/*.bst", "elements/**/*.bst"])
        output = subprocess.check_output(cmd_direct, text=True)
        return [line.strip() for line in output.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Base git commit/ref to compare against (default: HEAD)",
    )
    parser.add_argument(
        "--head",
        default=None,
        help="Head git commit/ref (if omitted, compares working tree against base)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional specific .bst files to check",
    )

    args = parser.parse_args(argv)

    files_to_check = args.files
    if not files_to_check:
        files_to_check = get_changed_files(args.base, args.head)

    errors: list[str] = []
    checked_count = 0

    for file_path in files_to_check:
        if not file_path.endswith(".bst"):
            continue

        base_content = get_git_file_content(args.base, file_path)
        if base_content is None:
            # File was added in this revision; nothing to diff against
            continue

        if args.head:
            head_content = get_git_file_content(args.head, file_path)
        else:
            disk_path = Path(file_path)
            if not disk_path.exists():
                # File was deleted in working tree
                continue
            head_content = disk_path.read_text(encoding="utf-8")

        if head_content is None:
            continue

        err = check_parity(file_path, base_content, head_content)
        checked_count += 1
        if err:
            errors.append(err)

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"OK: multi-arch ref parity check passed ({checked_count} element(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
