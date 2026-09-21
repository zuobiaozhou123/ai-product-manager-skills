#!/usr/bin/env python3
"""Deterministic inventory, manifest, and structural checks for a knowledge system."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


MANIFEST_NAME = ".knowledge-system.json"
MANIFEST_SCHEMA_VERSION = 2
REQUIRED_VALIDATION_STAGES = (
    "design_traceability",
    "retrieval",
    "durable_increment",
    "temporary_input",
    "change_impact",
    "linked_update",
    "consistency",
)
KNOWLEDGE_OBJECT_MANAGEMENT = {
    "section",
    "document_type",
    "metadata",
    "index",
    "external_reference",
    "merged",
}
NOISE_NAMES = {
    ".cache",
    ".git",
    ".idea",
    ".next",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class ToolError(Exception):
    """A user-correctable command error."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def existing_directory(raw: str, label: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise ToolError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise ToolError(f"{label} is not a directory: {path}")
    return path


def project_path(project: Path, raw: str, label: str, *, must_exist: bool = True) -> Path:
    relative = Path(raw)
    if relative.is_absolute():
        raise ToolError(f"{label} must be relative to the project: {raw}")
    candidate = (project / relative).resolve(strict=False)
    if not is_within(candidate, project):
        raise ToolError(f"{label} leaves the project: {raw}")
    if must_exist and not candidate.exists():
        raise ToolError(f"{label} does not exist: {raw}")
    return candidate


def relative_text(path: Path, project: Path) -> str:
    return path.relative_to(project).as_posix()


def classify_name(path: Path) -> str | None:
    lowered = path.name.lower()
    if lowered in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES:
        return "sensitive"
    if lowered in NOISE_NAMES:
        return "noise"
    return None


def inventory_entries(source: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    def visit(directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name.lower())
        except OSError as exc:
            entries.append(
                {
                    "path": relative_text(directory, source) or ".",
                    "kind": "directory",
                    "classification": "unreadable",
                    "error": str(exc),
                }
            )
            return

        for child in children:
            path = Path(child.path)
            relative = relative_text(path, source)
            named_classification = classify_name(path)

            if child.is_symlink():
                try:
                    target = path.resolve(strict=True)
                    classification = (
                        "internal-link" if is_within(target, source) else "external-link"
                    )
                    target_text = str(target)
                except OSError:
                    classification = "broken-link"
                    target_text = os.readlink(path)
                entries.append(
                    {
                        "path": relative,
                        "kind": "symlink",
                        "classification": classification,
                        "target": target_text,
                    }
                )
                continue

            if child.is_dir(follow_symlinks=False):
                classification = named_classification or "directory"
                entries.append(
                    {
                        "path": relative,
                        "kind": "directory",
                        "classification": classification,
                    }
                )
                if classification != "noise":
                    visit(path)
                continue

            try:
                stat = child.stat(follow_symlinks=False)
                size = stat.st_size
                modified_at = datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat()
            except OSError as exc:
                entries.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "classification": "unreadable",
                        "error": str(exc),
                    }
                )
                continue

            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "classification": named_classification or "candidate",
                    "size": size,
                    "modified_at": modified_at,
                }
            )

    visit(source)
    return entries


def load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"invalid {label}: {path}: {exc}") from exc


def normalize_confirmed_sections(raw: object) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(raw, list) or not raw:
        return [], ["design_traceability needs confirmed_sections"]

    sections: list[str] = []
    for index, item in enumerate(raw):
        prefix = f"design_traceability confirmed_sections[{index}]"
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix} must be a non-empty path")
            continue
        path = Path(item.strip())
        if path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
            errors.append(f"{prefix} must be a top-level relative directory")
            continue
        normalized = path.as_posix()
        if normalized in sections:
            errors.append(f"design_traceability has duplicate confirmed section: {normalized}")
            continue
        sections.append(normalized)
    return sections, errors


def validation_errors(
    project: Path,
    validation_path: Path,
    *,
    require_confirmed_sections: bool = False,
) -> list[str]:
    payload = load_json(validation_path, "validation record")
    if not isinstance(payload, dict):
        return ["validation record must be a JSON object"]

    errors: list[str] = []
    if payload.get("result") != "passed":
        errors.append("validation result must be passed")

    stages = payload.get("stages")
    if not isinstance(stages, dict):
        return errors + ["validation stages must be an object"]

    missing = [name for name in REQUIRED_VALIDATION_STAGES if name not in stages]
    if missing:
        errors.append("missing validation stages: " + ", ".join(missing))

    for name in REQUIRED_VALIDATION_STAGES:
        stage = stages.get(name)
        if stage is None:
            continue
        if not isinstance(stage, dict):
            errors.append(f"validation stage {name} must be an object")
            continue
        if stage.get("result") != "passed":
            errors.append(f"validation stage {name} must be passed")
        if not isinstance(stage.get("summary"), str) or not stage["summary"].strip():
            errors.append(f"validation stage {name} needs a summary")
        evidence = stage.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"validation stage {name} needs evidence")
            continue
        for raw in evidence:
            if not isinstance(raw, str):
                errors.append(f"validation stage {name} has a non-string evidence path")
                continue
            try:
                project_path(project, raw, f"validation evidence for {name}")
            except ToolError as exc:
                errors.append(str(exc))

        if name == "design_traceability":
            if stage.get("confirmed_by_user") is not True:
                errors.append(
                    "validation stage design_traceability must be confirmed_by_user"
                )
            objects = stage.get("knowledge_objects")
            if not isinstance(objects, list) or not objects:
                errors.append(
                    "validation stage design_traceability needs knowledge_objects"
                )
                continue
            seen_names: set[str] = set()
            for index, item in enumerate(objects):
                prefix = f"design_traceability knowledge_objects[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for field in ("name", "source", "target"):
                    value = item.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{prefix} needs {field}")
                object_name = item.get("name")
                if isinstance(object_name, str) and object_name.strip():
                    normalized_name = object_name.strip()
                    if normalized_name in seen_names:
                        errors.append(
                            f"design_traceability has duplicate knowledge object: {normalized_name}"
                        )
                    seen_names.add(normalized_name)
                management = item.get("management")
                if management not in KNOWLEDGE_OBJECT_MANAGEMENT:
                    errors.append(
                        f"{prefix} management must be one of: "
                        + ", ".join(sorted(KNOWLEDGE_OBJECT_MANAGEMENT))
                    )
                if management in {
                    "metadata",
                    "index",
                    "external_reference",
                    "merged",
                }:
                    rationale = item.get("rationale")
                    if not isinstance(rationale, str) or not rationale.strip():
                        errors.append(
                            f"{prefix} needs rationale when management is {management}"
                        )
            if require_confirmed_sections:
                confirmed_sections, section_errors = normalize_confirmed_sections(
                    stage.get("confirmed_sections")
                )
                errors.extend(section_errors)
                for raw in confirmed_sections:
                    try:
                        section_path = project_path(
                            project, raw, "confirmed top-level section"
                        )
                        if not section_path.is_dir():
                            errors.append(
                                f"confirmed top-level section is not a directory: {raw}"
                            )
                    except ToolError as exc:
                        errors.append(str(exc))
    return errors


def confirmed_sections_from_validation(validation_path: Path) -> list[str]:
    payload = load_json(validation_path, "validation record")
    if not isinstance(payload, dict):
        return []
    stages = payload.get("stages")
    if not isinstance(stages, dict):
        return []
    design = stages.get("design_traceability")
    if not isinstance(design, dict):
        return []
    sections, _ = normalize_confirmed_sections(design.get("confirmed_sections"))
    return sections


def actual_root_sections(project: Path) -> list[str]:
    sections: list[str] = []
    for child in sorted(project.iterdir(), key=lambda path: path.name.lower()):
        if child.name.startswith(".") or child.name.lower() in NOISE_NAMES:
            continue
        if child.is_dir():
            sections.append(child.name)
    return sections


def structure_errors(
    confirmed_sections: list[str],
    declared_sections: list[str],
    actual_sections: list[str],
) -> list[str]:
    errors: list[str] = []
    confirmed = set(confirmed_sections)
    declared = set(declared_sections)
    actual = set(actual_sections)

    missing_declared = sorted(confirmed - declared)
    unexpected_declared = sorted(declared - confirmed)
    if missing_declared:
        errors.append("missing declared sections: " + ", ".join(missing_declared))
    if unexpected_declared:
        errors.append("unexpected declared sections: " + ", ".join(unexpected_declared))

    missing_actual = sorted(confirmed - actual)
    unexpected_actual = sorted(actual - confirmed)
    if missing_actual:
        errors.append("missing root sections: " + ", ".join(missing_actual))
    if unexpected_actual:
        errors.append("unexpected root sections: " + ", ".join(unexpected_actual))
    return errors


def write_json(path: Path, payload: object, pretty: bool) -> None:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        sort_keys=True,
    )
    path.write_text(text + "\n", encoding="utf-8")


def print_json(payload: object, pretty: bool) -> None:
    json.dump(
        payload,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if pretty else None,
        sort_keys=True,
    )
    sys.stdout.write("\n")


def command_inventory(args: argparse.Namespace) -> int:
    source = existing_directory(args.source, "source")
    payload = {"source": str(source), "entries": inventory_entries(source)}
    print_json(payload, args.pretty)
    return 0


def command_manifest(args: argparse.Namespace) -> int:
    project = existing_directory(args.project, "project")
    root_rule = project_path(project, "AGENTS.md", "root rule")
    project_path(project, "index.md", "root index")

    sections: list[str] = []
    rule_files = [root_rule]
    for raw in args.section:
        section = project_path(project, raw, "section")
        if not section.is_dir():
            raise ToolError(f"section is not a directory: {raw}")
        normalized = relative_text(section, project)
        if normalized in sections:
            continue
        sections.append(normalized)
        rule_files.append(project_path(project, f"{normalized}/AGENTS.md", "section rule"))
        project_path(project, f"{normalized}/index.md", "section index")

    generated_files: list[str] = []
    for raw in args.generated_file:
        path = project_path(project, raw, "generated file")
        normalized = relative_text(path, project)
        if normalized not in generated_files:
            generated_files.append(normalized)

    validation_file: str | None = None
    confirmed_sections: list[str] = []
    if args.validation_file:
        validation_path = project_path(project, args.validation_file, "validation file")
        validation_file = relative_text(validation_path, project)
        errors = validation_errors(
            project,
            validation_path,
            require_confirmed_sections=args.status == "complete",
        )
        if args.status == "complete":
            confirmed_sections = confirmed_sections_from_validation(validation_path)
            errors.extend(
                structure_errors(
                    confirmed_sections,
                    sections,
                    actual_root_sections(project),
                )
            )
        if args.status == "complete" and errors:
            raise ToolError("; ".join(errors))
    elif args.status == "complete":
        raise ToolError("complete status requires --validation-file")

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": args.status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root_rule": "AGENTS.md",
        "root_index": "index.md",
        "sections": sorted(sections),
        "confirmed_sections": sorted(confirmed_sections),
        "generated_files": sorted(generated_files),
        "validation_file": validation_file,
        "rule_fingerprints": {
            relative_text(path, project): sha256(path) for path in sorted(rule_files)
        },
    }
    write_json(project / MANIFEST_NAME, manifest, True)
    print_json(manifest, args.pretty)
    return 0


def markdown_link_errors(project: Path) -> list[str]:
    errors: list[str] = []
    for document in sorted(project.rglob("*.md")):
        if document.is_symlink() or not document.is_file():
            continue
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read Markdown file {relative_text(document, project)}: {exc}")
            continue
        for match in MARKDOWN_LINK.finditer(text):
            raw = match.group(1).strip()
            if not raw:
                continue
            if raw.startswith("<") and ">" in raw:
                raw = raw[1 : raw.index(">")]
            else:
                raw = raw.split(maxsplit=1)[0]
            parsed = urlparse(raw)
            if parsed.scheme or raw.startswith("#"):
                continue
            target_text = unquote(raw.split("#", 1)[0])
            if not target_text:
                continue
            target = Path(target_text)
            if target.is_absolute():
                continue
            resolved = (document.parent / target).resolve(strict=False)
            source = relative_text(document, project)
            if not is_within(resolved, project):
                errors.append(f"Markdown link leaves project: {source} -> {raw}")
            elif not resolved.exists():
                errors.append(f"broken Markdown link: {source} -> {raw}")
    return errors


def command_diagnose(args: argparse.Namespace) -> int:
    project = existing_directory(args.project, "project")
    manifest_path = project / MANIFEST_NAME
    errors: list[str] = []
    warnings: list[str] = []
    status = "missing"

    if not manifest_path.exists():
        errors.append(f"missing manifest: {MANIFEST_NAME}")
        manifest: dict[str, object] = {}
    else:
        payload = load_json(manifest_path, "manifest")
        if not isinstance(payload, dict):
            errors.append("manifest must be a JSON object")
            manifest = {}
        else:
            manifest = payload
            status = str(manifest.get("status", "unknown"))

    if manifest:
        schema_version = manifest.get("schema_version")
        if schema_version not in {1, MANIFEST_SCHEMA_VERSION}:
            errors.append("unsupported manifest schema_version")
        elif schema_version == 1:
            warnings.append(
                "legacy manifest schema_version 1 does not verify confirmed root sections"
            )
        if status not in {"building", "complete", "incomplete"}:
            errors.append(f"invalid manifest status: {status}")

        for field in ("root_rule", "root_index"):
            raw = manifest.get(field)
            if not isinstance(raw, str):
                errors.append(f"manifest {field} must be a path")
                continue
            try:
                project_path(project, raw, field)
            except ToolError as exc:
                errors.append(str(exc))

        sections = manifest.get("sections", [])
        if not isinstance(sections, list):
            errors.append("manifest sections must be a list")
            sections = []
        for raw in sections:
            if not isinstance(raw, str):
                errors.append("manifest section path must be a string")
                continue
            for suffix, label in (("AGENTS.md", "section rule"), ("index.md", "section index")):
                try:
                    project_path(project, f"{raw}/{suffix}", label)
                except ToolError as exc:
                    errors.append(str(exc))

        if schema_version == MANIFEST_SCHEMA_VERSION:
            confirmed_raw = manifest.get("confirmed_sections")
            confirmed_sections, confirmed_errors = normalize_confirmed_sections(
                confirmed_raw
            )
            errors.extend(confirmed_errors)
            errors.extend(
                structure_errors(
                    confirmed_sections,
                    [raw for raw in sections if isinstance(raw, str)],
                    actual_root_sections(project),
                )
            )

        generated = manifest.get("generated_files", [])
        if not isinstance(generated, list):
            errors.append("manifest generated_files must be a list")
            generated = []
        for raw in generated:
            if not isinstance(raw, str):
                errors.append("generated file path must be a string")
                continue
            try:
                project_path(project, raw, "generated file")
            except ToolError as exc:
                errors.append(str(exc))

        fingerprints = manifest.get("rule_fingerprints", {})
        if not isinstance(fingerprints, dict):
            errors.append("manifest rule_fingerprints must be an object")
        else:
            for raw, expected in fingerprints.items():
                if not isinstance(raw, str) or not isinstance(expected, str):
                    errors.append("rule fingerprint entries must map paths to hashes")
                    continue
                try:
                    path = project_path(project, raw, "rule file")
                except ToolError as exc:
                    errors.append(str(exc))
                    continue
                if sha256(path) != expected:
                    warnings.append(f"rule file changed after generation: {raw}")

        validation_file = manifest.get("validation_file")
        if status == "complete":
            if not isinstance(validation_file, str):
                errors.append("complete status requires a validation file")
            else:
                try:
                    validation_path = project_path(
                        project, validation_file, "validation file"
                    )
                    errors.extend(
                        validation_errors(
                            project,
                            validation_path,
                            require_confirmed_sections=(
                                schema_version == MANIFEST_SCHEMA_VERSION
                            ),
                        )
                    )
                except ToolError as exc:
                    errors.append(str(exc))
        else:
            warnings.append(f"knowledge system status is {status}, not complete")

    errors.extend(markdown_link_errors(project))
    report = {
        "project": str(project),
        "status": status,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    print_json(report, args.pretty)
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="inventory existing materials")
    inventory.add_argument("--source", required=True)
    inventory.add_argument("--pretty", action="store_true")
    inventory.set_defaults(handler=command_inventory)

    manifest = subparsers.add_parser("manifest", help="write the project manifest")
    manifest.add_argument("--project", required=True)
    manifest.add_argument("--section", action="append", default=[])
    manifest.add_argument("--generated-file", action="append", default=[])
    manifest.add_argument("--validation-file")
    manifest.add_argument(
        "--status",
        choices=("building", "complete", "incomplete"),
        default="building",
    )
    manifest.add_argument("--pretty", action="store_true")
    manifest.set_defaults(handler=command_manifest)

    diagnose = subparsers.add_parser("diagnose", help="check project structure")
    diagnose.add_argument("--project", required=True)
    diagnose.add_argument("--pretty", action="store_true")
    diagnose.set_defaults(handler=command_diagnose)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except ToolError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
