#!/usr/bin/env python3
"""Dependency diagnostics inside a task image, not a task-validation verdict.

Inventory Python imports; probe unconditional external imports in isolated
subprocesses. Record context-dependent imports for the task's real launcher.
Inspect native ELF libraries with ldd. Findings are advisory: the launcher,
Smoke Judge and Full Judge establish runtime validity. Exit 1 means the scan
is incomplete (bad inputs, unreadable sources, unavailable tools or timeout),
not that the task is broken. Exit 0 means only that this diagnostic completed.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import subprocess
import sys
import sysconfig
import tokenize
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--sources", nargs="+", type=Path, required=True,
        help="directories or files whose Python imports must resolve",
    )
    parser.add_argument(
        "--ldd-roots", nargs="*", type=Path, default=None,
        help="directories to scan for shared objects (default: site-packages)",
    )
    parser.add_argument(
        "--ignore-modules", nargs="*", default=[],
        help="defer exact module names and descendants to real startup (no wildcards)",
    )
    parser.add_argument(
        "--import-path", nargs="+", type=Path, default=[],
        help="explicit import roots used by the real launcher, in search order; no launcher code is executed",
    )
    parser.add_argument(
        "--ignore-libs", nargs="*", default=[],
        help="additional missing-library name prefixes to treat as optional",
    )
    parser.add_argument("--report", type=Path, help="write a JSON report here")
    parser.add_argument(
        "--timeout", type=float, default=300.0,
        help="seconds allowed per module import (default 300)",
    )
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    if any(any(char in name for char in "*?[]") for name in args.ignore_modules):
        parser.error("--ignore-modules takes exact names or package prefixes, not wildcards")
    return args


SOURCE_EXCLUDES = {".git", ".venv", "venv", "__pycache__", ".tox", "node_modules"}


def readable_directory(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.R_OK | os.X_OK)


def walk_files(root: Path, *, sources: bool = False):
    def fail(error: OSError) -> None:
        raise error

    for directory, dirs, names in os.walk(root, onerror=fail):
        dirs[:] = sorted(d for d in dirs if not sources or d not in SOURCE_EXCLUDES)
        for name in sorted(names):
            yield Path(directory) / name


def python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            found = [p for p in walk_files(path, sources=True) if p.suffix == ".py"]
            if not found:
                raise ValueError(f"no Python sources found under {path}")
            files.extend(found)
        else:
            raise ValueError(f"source does not exist or is not a Python file/directory: {path}")
    return sorted(set(files))


def imported_modules(files: list[Path]) -> dict[str, list[dict]]:
    """Inventory imports with their source and execution context, without running sources."""
    modules: dict[str, list[dict]] = {}
    for file in files:
        try:
            with tokenize.open(file) as stream:
                source = stream.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeError) as error:
            modules[f"<syntax error> {file}: {error}"] = []
            continue

        class Imports(ast.NodeVisitor):
            context: tuple[str, ...] = ()

            def visit(self, node):
                previous = self.context
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    self.context += ("deferred function",)
                elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.ClassDef)) or type(node).__name__ in ("Match", "TryStar"):
                    self.context += ("conditional or initialization context",)
                result = super().visit(node)
                self.context = previous
                return result

            def record(self, node, name, statement):
                context = list(self.context)
                top = name.split(".")[0]
                if name.startswith("."):
                    context.append("relative import")
                elif (file.parent / f"{top}.py").is_file() or (file.parent / top).is_dir():
                    context.append("source-local import")
                modules.setdefault(statement, []).append(
                    {"file": str(file), "line": node.lineno, "context": context}
                )

            def visit_Import(self, node):
                for alias in node.names:
                    self.record(node, alias.name, f"import {alias.name}")

            def visit_ImportFrom(self, node):
                name = "." * node.level + (node.module or "")
                for alias in node.names:
                    self.record(node, name, f"from {name} import {alias.name}")

            def visit_Call(self, node):
                # Recognize the common forms; never evaluate computed module names.
                function = ""
                if isinstance(node.func, ast.Name):
                    function = node.func.id
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    function = f"{node.func.value.id}.{node.func.attr}"
                if function in ("importlib.import_module", "__import__"):
                    expression = ast.get_source_segment(source, node)
                    modules.setdefault(f"<dynamic import> {expression}", []).append(
                        {"file": str(file), "line": node.lineno,
                         "context": [*self.context, "dynamic import"]}
                    )
                self.generic_visit(node)

        Imports().visit(tree)
    return dict(sorted(modules.items()))


def import_target(statement: str) -> str:
    """Full requested name for exclusion matching and package classification."""
    if statement.startswith(("<syntax error>", "<dynamic import>")):
        return ""
    parts = statement.split()
    return parts[1] + (f".{parts[3]}" if parts[0] == "from" else "")


def try_import(statement: str, timeout: float, paths: list[Path]) -> tuple[bool, str]:
    if statement.startswith("<syntax error>"):
        return False, statement
    prelude = f"import sys; sys.path[:0] = {[str(p.resolve()) for p in paths]!r};\n" if paths else ""
    if statement.startswith("from __future__ import "):
        prelude = ""  # compiler directives must precede executable bootstrap code
    done = subprocess.run(
        [sys.executable, "-I", "-c", prelude + statement],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
    )
    if done.returncode == 0:
        return True, ""
    tail = (done.stderr or done.stdout).strip().splitlines()
    return False, "\n".join(tail[-8:])


def elf_identity(path: Path) -> tuple[int, int, int, int] | None:
    try:
        with path.open("rb") as stream:
            header = stream.read(20)
    except OSError as error:
        raise OSError(f"could not inspect ELF header for {path}: {error}") from error
    if header[:4] != b"\x7fELF":
        return None
    if len(header) < 20 or header[4] not in (1, 2) or header[5] not in (1, 2):
        raise OSError(f"invalid ELF header: {path}")
    order = "little" if header[5] == 1 else "big"
    return header[4], header[5], int.from_bytes(header[18:20], order), int.from_bytes(header[16:18], order)


def shared_objects(roots: list[Path], skipped: dict[str, str]) -> list[Path]:
    """Native shared-object candidates; record skipped formats/ABIs explicitly."""
    found: list[Path] = []
    native = elf_identity(Path(sys.executable))
    if native is None:
        raise OSError(f"cannot determine native ELF identity from {sys.executable}")
    for root in roots:
        for path in walk_files(root):
            if ".so" not in path.name:
                continue
            identity = elf_identity(path)
            if identity is None:
                skipped[str(path)] = "non-ELF file"
            elif identity[:3] != native[:3]:
                skipped[str(path)] = f"foreign ELF ABI {identity[:3]} (interpreter ABI {native[:3]})"
            elif identity[3] != 3:
                skipped[str(path)] = f"ELF type {identity[3]}, not a shared object"
            else:
                found.append(path)
    return sorted(set(found))


# Runtime libraries that packages load lazily for optional features (media codecs,
# RDMA, MPI, other Python ABIs, example plugins). Classification is a hint only.
OPTIONAL_LIB_PREFIXES = (
    "libav", "libsw", "libsox", "libmlx5", "librdmacm", "libibverbs", "libucp", "libmpi",
    "libcuda.so", "libnvidia-", "libpython3.", "usdResolverExample", "usdSchemaExamples",
)


def ldd_missing(objects: list[Path]) -> tuple[dict[str, list[str]], list[str]]:
    """Return missing-library needers (up to five each) and inspection errors."""
    missing: dict[str, list[str]] = {}
    errors: list[str] = []
    batch = 200
    for start in range(0, len(objects), batch):
        chunk = objects[start:start + batch]
        try:
            done = subprocess.run(
                ["ldd", *map(str, chunk)], capture_output=True, text=True, timeout=600,
            )
        except OSError as error:
            errors.append(f"could not execute ldd: {error}")
            break
        except subprocess.TimeoutExpired:
            errors.append(f"ldd did not finish within 600s (starting at {chunk[0]})")
            break
        if done.returncode != 0:
            detail = "\n".join((done.stderr or done.stdout).strip().splitlines()[-8:])
            errors.append(f"ldd exited with status {done.returncode}: {detail}")
        # ldd omits the object-name header when given exactly one object.
        current = str(chunk[0]) if len(chunk) == 1 else ""
        for line in done.stdout.splitlines():
            if not line.startswith(("\t", " ")) and line.endswith(":"):
                current = line[:-1]
                continue
            if "not found" not in line:
                continue
            name = line.strip().split(" ")[0]
            needers = missing.setdefault(name, [])
            if len(needers) < 5 and current not in needers:
                needers.append(current)
    return missing, errors


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    files: list[Path] = []
    for path in args.sources:
        try:
            files.extend(python_files([path]))
        except (OSError, ValueError) as error:
            errors.append(f"source scan: {error}")
    files = sorted(set(files))
    modules: dict[str, list[dict]] = {}
    for file in files:
        try:
            for statement, locations in imported_modules([file]).items():
                modules.setdefault(statement, []).extend(locations)
        except OSError as error:
            errors.append(f"could not read source {file}: {error}")
    for path in args.import_path:
        if not readable_directory(path):
            errors.append(f"import root is not a readable directory: {path}")
    ignored = set(args.ignore_modules)
    import_failures: dict[str, dict[str, object]] = {}
    deferred: dict[str, dict] = {}
    checked = 0
    for statement, locations in sorted(modules.items()):
        users = sorted({location["file"] for location in locations})
        if statement.startswith("<syntax error>"):
            errors.append(statement)
            import_failures[statement] = {"error": statement, "imported_by": users}
            continue
        target = import_target(statement)
        excluded = any(target == name or target.startswith(name + ".") for name in ignored)
        pending_locations = locations if excluded else [place for place in locations if place["context"]]
        if pending_locations:
            deferred[statement] = {
                "imported_by": sorted({place["file"] for place in pending_locations}),
                "locations": pending_locations,
                "reason": "explicit exclusion" if excluded else "requires source/launcher context",
            }
        if excluded or not any(not place["context"] for place in locations):
            continue
        checked += 1
        try:
            ok, detail = try_import(statement, args.timeout, args.import_path)
        except (OSError, subprocess.TimeoutExpired) as error:
            ok, detail = False, str(error)
            errors.append(f"could not complete {statement}: {error}")
        if not ok:
            import_failures[statement] = {"error": detail, "imported_by": users, "locations": locations}
    roots = args.ldd_roots
    if roots is None:
        roots = list(dict.fromkeys(Path(sysconfig.get_paths()[key]) for key in ("purelib", "platlib")))
    valid_roots = []
    for root in roots:
        if readable_directory(root):
            valid_roots.append(root)
        else:
            errors.append(f"library root is not a readable directory: {root}")
    skipped: dict[str, str] = {}
    objects: list[Path] = []
    try:
        if valid_roots:
            objects = shared_objects(valid_roots, skipped)
        missing, ldd_errors = ldd_missing(objects)
    except OSError as error:
        missing, ldd_errors = {}, [str(error)]
    errors.extend(ldd_errors)
    optional_prefixes = OPTIONAL_LIB_PREFIXES + tuple(args.ignore_libs)
    imported = {import_target(statement).split(".")[0] for statement in modules}
    imported.update(name.split(".")[0] for name in ignored)
    blocking: dict[str, list[str]] = {}
    optional: dict[str, list[str]] = {}
    unused: dict[str, list[str]] = {}
    candidates_by_name: dict[str, list[str]] = {}
    for path in objects:
        candidates_by_name.setdefault(path.name, []).append(str(path))
    found_under_roots: dict[str, dict[str, object]] = {}
    for name, needers in missing.items():
        if name in candidates_by_name:
            found_under_roots[name] = {
                "candidates": candidates_by_name[name],
                "needed_by": needers,
                "note": "loader path unverified",
            }
            continue
        packages = set()
        for needer in needers:
            for root in roots:
                try:
                    packages.add(Path(needer).relative_to(root).parts[0])
                    break
                except ValueError:
                    continue
        needed_by_task = bool(packages & imported)
        known_optional = name.startswith(optional_prefixes) or not name.startswith("lib")
        if needed_by_task and not known_optional:
            blocking[name] = needers          # prioritize investigation; not proof of runtime failure
        elif needed_by_task:
            optional[name] = needers          # lazily loaded feature of an imported package
        else:
            unused[name] = needers            # package the task never imports
    report = {
        "scan_status": "incomplete" if errors else "complete",
        "scan_errors": errors,
        "scope": "dependency diagnostics only; task startup and Judge must confirm runtime validity",
        "python": sys.version.split()[0],
        "sources": [str(p) for p in args.sources],
        "source_files": len(files),
        "imports_discovered": len(modules),
        "modules_checked": checked,
        "modules_ignored": sorted(ignored),
        "import_paths": [str(p) for p in args.import_path],
        "imports_deferred": deferred,
        "import_failures": import_failures,
        "ldd_roots": [str(r) for r in roots],
        "ldd_errors": ldd_errors,
        "shared_objects_checked": len(objects),
        "shared_objects_skipped": skipped,
        "missing_shared_libraries": blocking,
        "missing_optional_libraries": optional,
        "missing_libraries_of_unimported_packages": unused,
        "found_under_scanned_roots": found_under_roots,
    }
    if args.report:
        try:
            args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        except OSError as error:
            errors.append(f"could not write report {args.report}: {error}")
    print(f"sources: {len(files)}; imports probed: {checked}; deferred: {len(deferred)}; import findings: {len(import_failures)}")
    for module, info in import_failures.items():
        print(f"  {module}: {str(info['error']).splitlines()[-1] if info['error'] else ''}")
    print(f"library findings (advisory): {len(blocking)} in imported packages, {len(optional)} possibly optional, {len(unused)} in unimported packages; skipped formats/ABIs: {len(skipped)}")
    print(f"  {len(found_under_roots)} found under scanned roots (loader path unverified)")
    for name, needers in blocking.items():
        print(f"  {name}  (e.g. {needers[0] if needers else '?'})")
    for error in errors:
        print(f"  {error}")
    print("diagnostic scan:", "INCOMPLETE" if errors else "COMPLETE (not a task-validation verdict)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
