#!/usr/bin/env python3
"""
Dotfiles Synchronization & Backup Tool

Copies dotfiles from this repository to the user's home folder (or custom destination),
translating the 'dot_' naming prefix to actual dots ('.') in file and directory names.

Safety & Backup:
  - By default, runs in DRY-RUN mode. Changes are only applied when passing '--apply'.
  - If a destination file already exists, it is safely copied to a timestamped backup
    directory (preserving full directory hierarchy) before the original is overwritten.
  - Supports skipping files or folders via '--skip' command-line patterns or '--skip-file'
    text files (e.g. skip.txt or .syncignore).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import filecmp
import fnmatch
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Sequence

DEFAULT_IGNORE = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".dotfiles_backup",
    ".syncignore",
    "skip.txt",
}


def transform_name(name: str) -> str:
    """
    Replace 'dot_' with '.' according to chezmoi/dotfiles conventions.
    Leading 'dot_' becomes '.', and any other occurrences of 'dot_' in the name
    are replaced with '.'.
    """
    if name.startswith("dot_"):
        return "." + name[4:]
    return name.replace("dot_", ".")


def map_target_path(source_root: Path, file_path: Path, target_root: Path) -> Path:
    """
    Computes the target path in target_root corresponding to file_path in source_root,
    transforming each component with transform_name.
    """
    rel = file_path.relative_to(source_root)
    transformed_parts = [transform_name(part) for part in rel.parts]
    return target_root.joinpath(*transformed_parts)


def is_file_identical(src: Path, dst: Path) -> bool:
    """
    Returns True if dst exists, is a regular file, has the same size,
    and identical byte content to src.
    """
    if not dst.exists() or not dst.is_file():
        return False
    if src.stat().st_size != dst.stat().st_size:
        return False
    return filecmp.cmp(src, dst, shallow=False)


def safe_copy(src: Path, dst: Path) -> None:
    """
    Safely copies src to dst, ensuring destination directories exist and
    handling read-only permissions gracefully.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            dst.chmod(stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
    shutil.copy2(src, dst)


def read_skip_file(file_path: Path) -> list[str]:
    """Reads skip patterns from a text file, ignoring blank lines and # comments."""
    if not file_path.exists():
        raise FileNotFoundError(f"Skip file not found: {file_path}")
    patterns: list[str] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)
    return patterns


def load_skip_patterns(
    cli_skips: Sequence[str] | None,
    skip_file_arg: Path | None,
    source_dir: Path,
) -> tuple[list[str], str | None]:
    """
    Consolidates skip patterns from CLI arguments and text files.
    Returns (patterns_list, source_description).
    """
    patterns: list[str] = []
    source_descriptions: list[str] = []

    # 1. From CLI arguments (handling comma separation and whitespace)
    if cli_skips:
        cli_count = 0
        for item in cli_skips:
            for sub_item in item.split(","):
                cleaned = sub_item.strip()
                if cleaned:
                    patterns.append(cleaned)
                    cli_count += 1
        if cli_count > 0:
            source_descriptions.append(f"{cli_count} from CLI --skip")

    # 2. From explicit --skip-file
    if skip_file_arg:
        resolved = skip_file_arg.resolve()
        file_patterns = read_skip_file(resolved)
        patterns.extend(file_patterns)
        source_descriptions.append(f"{len(file_patterns)} from '{skip_file_arg.name}'")
    else:
        # 3. Auto-detect .syncignore or skip.txt if present in source repo
        for auto_candidate in (".syncignore", "skip.txt"):
            auto_path = source_dir / auto_candidate
            if auto_path.is_file():
                file_patterns = read_skip_file(auto_path)
                patterns.extend(file_patterns)
                source_descriptions.append(f"{len(file_patterns)} from auto-detected '{auto_candidate}'")
                break

    desc = ", ".join(source_descriptions) if source_descriptions else None
    return patterns, desc


def should_skip(
    rel_src: Path,
    rel_tgt: Path,
    patterns: Sequence[str],
) -> tuple[bool, str]:
    """
    Checks if a relative path (source or target) matches any skip pattern.
    Supports exact file/dir names, path prefixes, and glob patterns.
    Returns (True, matching_pattern) if it matches, else (False, "").
    """
    src_posix = rel_src.as_posix()
    tgt_posix = rel_tgt.as_posix()

    src_parts = rel_src.parts
    tgt_parts = rel_tgt.parts

    for pat in patterns:
        clean_pat = pat.strip()
        if not clean_pat or clean_pat.startswith("#"):
            continue

        p = clean_pat.replace("\\", "/").rstrip("/")

        # 1. Exact or glob match against full relative path
        if fnmatch.fnmatch(src_posix, p) or fnmatch.fnmatch(tgt_posix, p):
            return True, clean_pat

        # 2. Directory prefix match (e.g. pattern 'dot_gemini' matches 'dot_gemini/sub/file')
        if src_posix.startswith(p + "/") or tgt_posix.startswith(p + "/"):
            return True, clean_pat

        # 3. Component match (e.g. pattern matches filename or any directory component)
        if any(fnmatch.fnmatch(part, p) for part in src_parts):
            return True, clean_pat
        if any(fnmatch.fnmatch(part, p) for part in tgt_parts):
            return True, clean_pat

    return False, ""


@dataclass
class SyncAction:
    source_path: Path
    target_path: Path
    rel_source_path: Path
    rel_target_path: Path
    backup_path: Path | None
    target_exists: bool
    is_identical: bool
    status: str  # "CREATE", "OVERWRITE", "SKIPPED_IDENTICAL", "SKIPPED_EXCLUDED"
    skip_reason: str | None = None


def collect_source_files(
    source_dir: Path,
    self_filename: str,
    extra_ignores: set[str] | None = None,
) -> list[Path]:
    """
    Recursively collects all files from source_dir, excluding ignored directories
    (like .git) and the script itself.
    """
    ignores = DEFAULT_IGNORE.union(extra_ignores or set())
    collected: list[Path] = []

    for root_str, dirs, files in os.walk(source_dir):
        root = Path(root_str)
        # Prune ignored directories in-place so os.walk does not traverse them
        dirs[:] = [
            d
            for d in dirs
            if d not in ignores and not d.startswith(".git")
        ]

        rel_root = root.relative_to(source_dir)
        if any(
            part in ignores or part.startswith(".git")
            for part in rel_root.parts
        ):
            continue

        for filename in files:
            if filename in ignores:
                continue
            if filename == self_filename:
                continue
            if filename.endswith(".pyc"):
                continue
            collected.append(root / filename)

    collected.sort()
    return collected


def plan_sync(
    source_dir: Path,
    target_dir: Path,
    backup_dir: Path | None,
    skip_identical: bool,
    skip_patterns: Sequence[str],
    self_filename: str,
    extra_ignores: set[str] | None = None,
) -> list[SyncAction]:
    """
    Scans source files, maps them to their target paths, checks skip rules,
    checks whether destination files exist or differ, and prepares the list of sync actions.
    """
    files = collect_source_files(source_dir, self_filename, extra_ignores=extra_ignores)
    actions: list[SyncAction] = []

    for src in files:
        rel_src = src.relative_to(source_dir)
        target = map_target_path(source_dir, src, target_dir)
        rel_target = target.relative_to(target_dir)

        # Check if user specified this file/folder to be skipped
        is_skipped, matched_pat = should_skip(rel_src, rel_target, skip_patterns)
        if is_skipped:
            actions.append(
                SyncAction(
                    source_path=src,
                    target_path=target,
                    rel_source_path=rel_src,
                    rel_target_path=rel_target,
                    backup_path=None,
                    target_exists=target.exists(),
                    is_identical=False,
                    status="SKIPPED_EXCLUDED",
                    skip_reason=f"matches '{matched_pat}'",
                )
            )
            continue

        target_exists = target.exists()
        identical = False
        if target_exists and target.is_file():
            identical = is_file_identical(src, target)

        if not target_exists:
            status = "CREATE"
            backup_path = None
        elif identical and skip_identical:
            status = "SKIPPED_IDENTICAL"
            backup_path = None
        else:
            status = "OVERWRITE"
            backup_path = backup_dir.joinpath(rel_target) if backup_dir else None

        actions.append(
            SyncAction(
                source_path=src,
                target_path=target,
                rel_source_path=rel_src,
                rel_target_path=rel_target,
                backup_path=backup_path,
                target_exists=target_exists,
                is_identical=identical,
                status=status,
            )
        )

    return actions


def print_plan(
    actions: list[SyncAction],
    source_dir: Path,
    target_dir: Path,
    backup_dir: Path | None,
    skip_summary: str | None,
    apply: bool,
    verbose: bool,
) -> None:
    """Displays a formatted table and summary of all planned operations."""
    mode_header = "[APPLY MODE]" if apply else "[DRY-RUN MODE]"
    print(f"\n{mode_header} Dotfiles Sync")
    print(f"  Source:    {source_dir}")
    print(f"  Target:    {target_dir}")
    if backup_dir:
        print(f"  Backup:    {backup_dir}")
    if skip_summary:
        print(f"  Skip list: {skip_summary}")
    print("-" * 85)
    print(f"{'ACTION':<22} {'SOURCE':<28} -> {'TARGET':<28}")
    print("-" * 85)

    create_count = 0
    overwrite_count = 0
    skipped_identical_count = 0
    skipped_excluded_count = 0

    for act in actions:
        src_disp = act.rel_source_path.as_posix()
        tgt_disp = act.rel_target_path.as_posix()

        if act.status == "CREATE":
            create_count += 1
            print(f"{'CREATE':<22} {src_disp:<28} -> {tgt_disp:<28}")
        elif act.status == "OVERWRITE":
            overwrite_count += 1
            note = "(identical)" if act.is_identical else "(modified)"
            action_label = f"OVERWRITE {note}"
            print(f"{action_label:<22} {src_disp:<28} -> {tgt_disp:<28}")
        elif act.status == "SKIPPED_EXCLUDED":
            skipped_excluded_count += 1
            action_label = f"SKIP ({act.skip_reason})"
            print(f"{action_label:<22} {src_disp:<28} -> {tgt_disp:<28}")
        elif act.status == "SKIPPED_IDENTICAL":
            skipped_identical_count += 1
            if verbose:
                print(f"{'SKIP (IDENTICAL)':<22} {src_disp:<28} -> {tgt_disp:<28}")

    if not verbose and skipped_identical_count > 0:
        print(f"({'and ' + str(skipped_identical_count) + ' identical file(s) omitted; use -v to show all'})")

    print("-" * 85)
    print("Summary:")
    print(f"  Total scanned:      {len(actions)}")
    print(f"  New (create):       {create_count}")
    print(f"  Existing (backup):  {overwrite_count}")
    print(f"  Skipped (excluded): {skipped_excluded_count}")
    print(f"  Skipped (identical):{skipped_identical_count}")

    if not apply:
        print("\n" + "=" * 85)
        print(">> DRY-RUN ONLY. No changes were made to disk.")
        print(">> To apply these changes and back up existing files, run:")
        print("       python sync.py --apply")
        print("=" * 85 + "\n")


def execute_plan(
    actions: list[SyncAction],
    backup_dir: Path | None,
    verbose: bool,
) -> int:
    """
    Executes the sync operations:
    1. Backs up existing files to backup_dir before touching them.
    2. Overwrites or creates target files.
    Returns the number of errors encountered.
    """
    errors = 0
    backed_up = 0
    copied = 0

    # Collect actions that require backup
    needs_backup = [a for a in actions if a.backup_path is not None]
    if needs_backup and backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)

    print("\nApplying changes...")

    # Step 1: Perform backups
    for act in needs_backup:
        assert act.backup_path is not None
        try:
            safe_copy(act.target_path, act.backup_path)
            backed_up += 1
            if verbose:
                print(f"  [BACKUP] {act.rel_target_path.as_posix()} -> {act.backup_path}")
        except Exception as err:
            print(f"  [ERROR] Failed to backup {act.target_path}: {err}", file=sys.stderr)
            errors += 1

    # Step 2: Perform copies
    for act in actions:
        if act.status in ("CREATE", "OVERWRITE"):
            try:
                safe_copy(act.source_path, act.target_path)
                copied += 1
                if verbose:
                    print(f"  [COPIED] {act.rel_source_path.as_posix()} -> {act.rel_target_path.as_posix()}")
            except Exception as err:
                print(f"  [ERROR] Failed to copy {act.source_path} to {act.target_path}: {err}", file=sys.stderr)
                errors += 1

    print("-" * 85)
    if errors == 0:
        print(f"SUCCESS: Synced {copied} file(s).")
        if backed_up > 0 and backup_dir:
            print(f"         Backed up {backed_up} existing file(s) to:")
            print(f"         {backup_dir}")
    else:
        print(f"COMPLETED WITH {errors} ERROR(S).", file=sys.stderr)

    return errors


def restore_backup(backup_source: Path, target_dir: Path, apply: bool, verbose: bool) -> int:
    """Restores files from a backup directory back to target_dir."""
    if not backup_source.exists() or not backup_source.is_dir():
        print(f"Error: Backup directory not found: {backup_source}", file=sys.stderr)
        return 1

    files_to_restore: list[Path] = []
    for root_str, _, files in os.walk(backup_source):
        root = Path(root_str)
        for f in files:
            files_to_restore.append(root / f)

    files_to_restore.sort()
    mode_str = "[APPLY MODE]" if apply else "[DRY-RUN MODE]"
    print(f"\n{mode_str} Restoring Backup")
    print(f"  Backup Source: {backup_source}")
    print(f"  Restore Target: {target_dir}")
    print("-" * 85)

    for src in files_to_restore:
        rel = src.relative_to(backup_source)
        dst = target_dir / rel
        print(f"  RESTORE {rel.as_posix()} -> {dst}")

    print("-" * 85)
    print(f"Total files to restore: {len(files_to_restore)}")

    if not apply:
        print("\n>> Dry-run only. To restore files, run:")
        print(f"       python sync.py --restore \"{backup_source}\" --apply\n")
        return 0

    errors = 0
    restored = 0
    for src in files_to_restore:
        rel = src.relative_to(backup_source)
        dst = target_dir / rel
        try:
            safe_copy(src, dst)
            restored += 1
            if verbose:
                print(f"  [RESTORED] {rel.as_posix()}")
        except Exception as err:
            print(f"  [ERROR] Could not restore {src} to {dst}: {err}", file=sys.stderr)
            errors += 1

    if errors == 0:
        print(f"\nSUCCESS: Restored {restored} file(s) from backup.")
    else:
        print(f"\nCompleted with {errors} error(s).", file=sys.stderr)
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync dotfiles to home folder with automatic backup of existing files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sync.py                            # Dry-run: preview files to copy and backup
  python sync.py --apply                    # Execute the sync and backup existing files
  python sync.py --skip dot_gemini *.conf   # Skip specific files or folders
  python sync.py --skip-file skip.txt       # Skip items defined in a .txt file
  python sync.py --skip-identical           # Skip files that already have identical content
  python sync.py --restore <dir>            # Restore files from a previous backup directory
        """,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, the script runs in dry-run preview mode.",
    )
    parser.add_argument(
        "--source",
        "-s",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Source dotfiles repository directory (default: current script directory).",
    )
    parser.add_argument(
        "--target",
        "--dest",
        "-d",
        type=Path,
        default=Path.home(),
        help="Destination directory (default: user home folder ~).",
    )
    parser.add_argument(
        "--backup-dir",
        "-b",
        type=Path,
        default=None,
        help="Custom directory to store backups of existing files (default: ~/.dotfiles_backup/<timestamp>).",
    )
    parser.add_argument(
        "--skip",
        action="extend",
        nargs="+",
        metavar="PATTERN",
        help="Files, folders, or glob patterns to skip (e.g. --skip dot_gemini dot_ideavimrc *.conf).",
    )
    parser.add_argument(
        "--skip-file",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to a .txt file with files/folders to skip (one per line, # for comments).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Disable backing up existing files before overwriting.",
    )
    parser.add_argument(
        "--skip-identical",
        action="store_true",
        help="Skip backing up and copying files that already exist with identical content.",
    )
    parser.add_argument(
        "--restore",
        type=Path,
        default=None,
        metavar="BACKUP_PATH",
        help="Restore files from a specified backup folder back to the target directory.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output for every file processed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_dir = args.source.resolve()
    target_dir = args.target.resolve()

    if args.restore:
        return restore_backup(
            backup_source=args.restore.resolve(),
            target_dir=target_dir,
            apply=args.apply,
            verbose=args.verbose,
        )

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Error: Source directory does not exist: {source_dir}", file=sys.stderr)
        return 1

    # Load skip patterns from CLI and/or skip file
    try:
        skip_patterns, skip_desc = load_skip_patterns(
            cli_skips=args.skip,
            skip_file_arg=args.skip_file,
            source_dir=source_dir,
        )
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    # Determine backup directory
    if args.no_backup:
        backup_dir = None
    elif args.backup_dir:
        backup_dir = args.backup_dir.resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = target_dir / ".dotfiles_backup" / timestamp

    self_filename = Path(__file__).name
    extra_ignores = set()
    if args.skip_file:
        extra_ignores.add(args.skip_file.name)

    actions = plan_sync(
        source_dir=source_dir,
        target_dir=target_dir,
        backup_dir=backup_dir,
        skip_identical=args.skip_identical,
        skip_patterns=skip_patterns,
        self_filename=self_filename,
        extra_ignores=extra_ignores,
    )

    print_plan(
        actions=actions,
        source_dir=source_dir,
        target_dir=target_dir,
        backup_dir=backup_dir if any(a.backup_path for a in actions) else None,
        skip_summary=skip_desc,
        apply=args.apply,
        verbose=args.verbose,
    )

    if args.apply:
        return execute_plan(
            actions=actions,
            backup_dir=backup_dir,
            verbose=args.verbose,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
