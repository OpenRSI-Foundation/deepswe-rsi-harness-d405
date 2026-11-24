#!/usr/bin/env python3
"""Split a finalized log into lossless ordinary-Git chunks, or verify and restore it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


MAX_CHUNK = 80 * 1024 * 1024
IO_BLOCK = 1024 * 1024


def _safe_path(path):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError(f"symlink paths are not allowed: {path}")
    return path


def _basename(name):
    return (isinstance(name, str) and name not in ("", ".", "..")
            and not any(char in name for char in ("/", "\\", "\x00")))


def _open_regular(path):
    path = _safe_path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"not a regular file: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        os.close(fd)
        raise ValueError(f"not a regular file, or hard-linked: {path}")
    return os.fdopen(fd, "rb")


def _part_name(index):
    return f"part-{index:06d}.bin"


def split_log(source, chunk_size=MAX_CHUNK):
    """Create <source>.parts, preserving source; refuse existing destinations."""
    if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK:
        raise ValueError("chunk size must be a positive integer of at most 80 MiB")
    source = _safe_path(source)
    if not _basename(source.name):
        raise ValueError("source filename must be a safe basename")
    directory = source.with_name(source.name + ".parts")
    created = []
    with _open_regular(source) as stream:
        before = os.fstat(stream.fileno())
        directory.mkdir()  # Exclusive: never reuse or clean an existing directory.
        try:
            total_hash, parts, remaining = hashlib.sha256(), [], before.st_size
            while remaining:
                name = _part_name(len(parts) + 1)
                path = directory / name
                part_size = min(chunk_size, remaining)
                part_hash, left = hashlib.sha256(), part_size
                with path.open("xb") as output:
                    created.append(path)
                    while left:
                        block = stream.read(min(IO_BLOCK, left))
                        if not block:
                            raise ValueError("source changed while splitting; use a finalized log")
                        output.write(block)
                        part_hash.update(block)
                        total_hash.update(block)
                        left -= len(block)
                parts.append({"file": name, "size": part_size, "sha256": part_hash.hexdigest()})
                remaining -= part_size
            after = os.fstat(stream.fileno())
            if (stream.read(1) or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns):
                raise ValueError("source changed while splitting; use a finalized log")
            manifest = {"version": 1, "source_name": source.name,
                        "source_size": before.st_size, "source_sha256": total_hash.hexdigest(),
                        "chunk_size": chunk_size, "parts": parts}
            path = directory / ".gitattributes"
            with path.open("x", encoding="ascii") as output:
                created.append(path)
                output.write("part-*.bin -text -filter\n")
            path = directory / "manifest.json"
            with path.open("x", encoding="utf-8") as output:
                created.append(path)
                json.dump(manifest, output, indent=2, ensure_ascii=True)
                output.write("\n")
        except BaseException:
            for path in reversed(created):
                path.unlink()
            directory.rmdir()
            raise
    return directory


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate manifest key: {key}")
        value[key] = item
    return value


def _is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _load_manifest(directory):
    with _open_regular(directory / "manifest.json") as stream:
        raw = stream.read(MAX_CHUNK + 1)
    if len(raw) > MAX_CHUNK:
        raise ValueError("manifest exceeds 80 MiB")
    try:
        manifest = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid manifest encoding or nesting") from error
    fields = {"version", "source_name", "source_size", "source_sha256", "chunk_size", "parts"}
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ValueError("invalid manifest fields")
    if (type(manifest["version"]) is not int or manifest["version"] != 1
            or not _basename(manifest["source_name"])
            or type(manifest["source_size"]) is not int or manifest["source_size"] < 0
            or not _is_hash(manifest["source_sha256"])
            or type(manifest["chunk_size"]) is not int
            or not 1 <= manifest["chunk_size"] <= MAX_CHUNK
            or not isinstance(manifest["parts"], list)):
        raise ValueError("invalid manifest metadata")
    remaining = manifest["source_size"]
    for index, part in enumerate(manifest["parts"], start=1):
        if (not isinstance(part, dict) or set(part) != {"file", "size", "sha256"}
                or part["file"] != _part_name(index)
                or type(part["size"]) is not int or part["size"] <= 0
                or part["size"] != min(manifest["chunk_size"], remaining)
                or not _is_hash(part["sha256"])):
            raise ValueError("invalid part metadata or order")
        remaining -= part["size"]
    if remaining != 0:
        raise ValueError("manifest part sizes do not match source size")
    return manifest


def restore_log(directory, output):
    """Verify every byte, then atomically publish a new output without overwrite."""
    directory, output = _safe_path(directory), _safe_path(output)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    manifest = _load_manifest(directory)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".restore-log-", delete=False) as target:
            temporary = Path(target.name)
            total_hash, total_size = hashlib.sha256(), 0
            for part in manifest["parts"]:
                part_hash, size = hashlib.sha256(), 0
                with _open_regular(directory / part["file"]) as stream:
                    if os.fstat(stream.fileno()).st_size != part["size"]:
                        raise ValueError(f"part size mismatch: {part['file']}")
                    while block := stream.read(IO_BLOCK):
                        size += len(block)
                        if size > part["size"]:
                            raise ValueError(f"part grew while reading: {part['file']}")
                        target.write(block)
                        part_hash.update(block)
                        total_hash.update(block)
                if size != part["size"] or part_hash.hexdigest() != part["sha256"]:
                    raise ValueError(f"part checksum mismatch: {part['file']}")
                total_size += size
            if (total_size != manifest["source_size"]
                    or total_hash.hexdigest() != manifest["source_sha256"]):
                raise ValueError("source checksum or size mismatch")
            target.flush()
            os.fsync(target.fileno())
        _safe_path(output)
        # link() publishes atomically and refuses even a concurrently created output.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink()
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    split = commands.add_parser("split", help="create uncompressed chunks and SHA-256 manifest")
    split.add_argument("file", type=Path)
    split.add_argument("--chunk-mib", type=int, choices=range(1, 81), default=80, metavar="1..80")
    restore = commands.add_parser("restore", help="verify chunks and restore to a new file")
    restore.add_argument("parts_dir", type=Path)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            print(split_log(args.file, args.chunk_mib * 1024 * 1024))
            print("Stage only the .parts directory; do not stage the original file.")
        else:
            print(restore_log(args.parts_dir, args.output))
    except (OSError, ValueError) as error:
        print(f"Log splitting/restoration error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
