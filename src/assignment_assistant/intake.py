"""Read-only source inventory, hashing, deduplication and text derivation."""

from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .storage import WorkspaceError, write_json


TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".csv", ".tsv", ".srt", ".vtt"}
ZIP_XML_EXTENSIONS = {".docx", ".pptx", ".odt"}
MAX_XML_MEMBER_BYTES = 20 * 1024 * 1024
MAX_TOTAL_XML_BYTES = 100 * 1024 * 1024
GOVERNING_TERMS = (
    "brief",
    "rubric",
    "marking",
    "assessment",
    "assignment",
    "learning outcome",
    "submission",
    "module handbook",
    "faq",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SourceRecord:
    path: str
    sha256: str
    size_bytes: int
    extension: str
    media_type: str
    duplicate_of: Optional[str]
    governing_candidate: bool
    extraction_status: str
    reading_copy: Optional[str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type_for(path: Path) -> str:
    return {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".srt": "application/x-subrip",
        ".vtt": "text/vtt",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".odt": "application/vnd.oasis.opendocument.text",
        ".mp4": "video/mp4",
    }.get(path.suffix.lower(), "application/octet-stream")


def _decode_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _natural_key(name: str) -> List[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _zip_xml_members(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    extension = path.suffix.lower()
    if extension == ".docx":
        preferred = [name for name in names if name == "word/document.xml"]
        preferred += sorted(
            (name for name in names if name.startswith("word/footnotes") or name.startswith("word/endnotes")),
            key=_natural_key,
        )
        return preferred
    if extension == ".pptx":
        slides = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=_natural_key,
        )
        notes = sorted(
            (name for name in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)),
            key=_natural_key,
        )
        return slides + notes
    if extension == ".odt" and "content.xml" in names:
        return ["content.xml"]
    return []


def _extract_xml_text(xml_bytes: bytes) -> str:
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def extract_text(path: Path) -> Tuple[Optional[str], str]:
    suffix = path.suffix.lower()
    try:
        if suffix in TEXT_EXTENSIONS:
            return _decode_text(path), "text"
        if suffix in ZIP_XML_EXTENSIONS:
            sections: List[str] = []
            total_uncompressed = 0
            with zipfile.ZipFile(path) as archive:
                for member in _zip_xml_members(path):
                    member_size = archive.getinfo(member).file_size
                    total_uncompressed += member_size
                    if member_size > MAX_XML_MEMBER_BYTES or total_uncompressed > MAX_TOTAL_XML_BYTES:
                        return None, "extraction-size-limit"
                    body = _extract_xml_text(archive.read(member))
                    if body:
                        sections.append(f"## {member}\n\n{body}")
            if sections:
                return "\n\n".join(sections), "derived-xml"
            return None, "no-readable-xml"
        if suffix == ".mp4":
            return None, "transcription-required"
        if suffix == ".pdf":
            return None, "pdf-extractor-required"
        return None, "unsupported"
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        return None, f"extraction-error:{type(exc).__name__}"


def _safe_derived_name(relative: Path) -> str:
    stem = "--".join(relative.with_suffix("").parts)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "source"
    return f"{stem}.md"


def iter_source_files(source_dir: Path) -> Iterable[Path]:
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        if any(part.startswith(".") for part in relative.parts) or path.name.startswith("~$"):
            continue
        yield path


def selected_source_files(workspace: Path, selections: Sequence[str]) -> List[Path]:
    """Resolve an explicit source selection without admitting ambient workspace files."""

    source_dir = (workspace / "source").resolve()
    selected: List[Path] = []
    seen = set()
    for value in selections:
        supplied = Path(value)
        candidate = supplied if supplied.is_absolute() else workspace / supplied
        resolved = candidate.expanduser().resolve()
        try:
            resolved.relative_to(source_dir)
        except ValueError as exc:
            raise WorkspaceError(
                f"Selected assignment source must be inside {source_dir}: {resolved}"
            ) from exc
        candidates = list(iter_source_files(resolved)) if resolved.is_dir() else [resolved]
        for path in candidates:
            if path.is_symlink() or not path.is_file():
                raise WorkspaceError(f"Selected assignment source is not a regular file: {path}")
            relative = path.relative_to(source_dir)
            if any(part.startswith(".") for part in relative.parts) or path.name.startswith("~$"):
                continue
            key = str(path)
            if key not in seen:
                selected.append(path)
                seen.add(key)
    if not selected:
        raise WorkspaceError(
            "No explicitly selected source files were found. Ask the user to provide or identify "
            "the assignment material to use."
        )
    return sorted(selected)


def run_intake(workspace: Path, selections: Sequence[str]) -> Dict[str, object]:
    workspace = workspace.expanduser().resolve()
    source_dir = workspace / "source"
    derived_dir = workspace / "derived" / "reading"
    research_dir = workspace / "assignment" / "research"
    source_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)
    research_dir.mkdir(parents=True, exist_ok=True)

    canonical_by_hash: Dict[str, str] = {}
    records: List[SourceRecord] = []
    routing_text_parts: List[str] = []
    provenance: List[Dict[str, str]] = []

    selected_files = selected_source_files(workspace, selections)
    for path in selected_files:
        relative = path.relative_to(workspace)
        digest = sha256_file(path)
        duplicate_of = canonical_by_hash.get(digest)
        if duplicate_of is None:
            canonical_by_hash[digest] = relative.as_posix()

        if duplicate_of is None:
            extracted, extraction_status = extract_text(path)
        else:
            extracted, extraction_status = None, "duplicate-skipped"
        reading_copy: Optional[str] = None
        if duplicate_of is None and extracted:
            routing_text_parts.append(path.name)
            routing_text_parts.append(extracted[:20000])
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                target = derived_dir / _safe_derived_name(path.relative_to(source_dir))
                target.write_text(
                    f"# Derived reading copy: {path.name}\n\n"
                    f"> Source: `{relative.as_posix()}`  \n"
                    f"> SHA-256: `{digest}`  \n"
                    f"> Extractor: `{extraction_status}`\n\n"
                    f"{extracted}\n",
                    encoding="utf-8",
                )
                reading_copy = target.relative_to(workspace).as_posix()
                provenance.append(
                    {
                        "source": relative.as_posix(),
                        "source_sha256": digest,
                        "derived": reading_copy,
                        "derived_sha256": sha256_file(target),
                        "method": extraction_status,
                        "verification_status": "unchecked",
                        "registered_at": utc_now(),
                    }
                )
        elif duplicate_of is None:
            routing_text_parts.append(path.name)

        lowered_name = path.name.lower()
        governing = any(term in lowered_name for term in GOVERNING_TERMS)
        records.append(
            SourceRecord(
                path=relative.as_posix(),
                sha256=digest,
                size_bytes=path.stat().st_size,
                extension=path.suffix.lower(),
                media_type=media_type_for(path),
                duplicate_of=duplicate_of,
                governing_candidate=governing,
                extraction_status=extraction_status,
                reading_copy=reading_copy,
            )
        )

    if not records:
        raise WorkspaceError(
            f"No source files found in {source_dir}. Add the assignment brief and course material first."
        )

    manifest_path = research_dir / "source-manifest.json"
    manifest = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "workspace_source": "source",
        "source_count": len(records),
        "unique_hash_count": len(canonical_by_hash),
        "duplicate_count": len(records) - len(canonical_by_hash),
        "records": [asdict(record) for record in records],
    }
    write_json(manifest_path, manifest)
    provenance_path = research_dir / "derivation-provenance.json"
    existing_provenance: List[Dict[str, str]] = []
    if provenance_path.exists():
        try:
            existing_payload = json.loads(provenance_path.read_text(encoding="utf-8"))
            existing_provenance = list(existing_payload.get("records", []))
        except json.JSONDecodeError as exc:
            raise WorkspaceError(f"Invalid provenance file: {provenance_path}") from exc
    seen_pairs = {
        (record.get("source_sha256"), record.get("derived_sha256"))
        for record in existing_provenance
    }
    for record in provenance:
        pair = (record.get("source_sha256"), record.get("derived_sha256"))
        if pair not in seen_pairs:
            existing_provenance.append(record)
            seen_pairs.add(pair)
    write_json(provenance_path, {"records": existing_provenance})

    index_path = workspace / "SOURCE_INDEX.md"
    index_path.write_text(render_source_index(records), encoding="utf-8")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path.relative_to(workspace).as_posix(),
        "index_path": index_path.relative_to(workspace).as_posix(),
        "routing_text": "\n".join(routing_text_parts),
        "registered_sources": [
            path.relative_to(workspace).as_posix() for path in selected_files
        ],
    }


def render_source_index(records: List[SourceRecord]) -> str:
    unique_count = sum(1 for record in records if record.duplicate_of is None)
    lines = [
        "# Source Index",
        "",
        "Generated by Academic Assignment Assistant. Originals remain in `source/`.",
        "",
        f"- Files found: {len(records)}",
        f"- Unique file hashes: {unique_count}",
        f"- Exact duplicate placements: {len(records) - unique_count}",
        "",
        "| Source | SHA-256 | Role hint | Extraction | Reading copy / duplicate |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        role = "governing candidate" if record.governing_candidate else "course/source material"
        relation = record.duplicate_of or record.reading_copy or "—"
        lines.append(
            f"| `{record.path}` | `{record.sha256[:12]}` | {role} | "
            f"{record.extraction_status} | `{relation}` |"
        )
    lines.extend(
        [
            "",
            "## Intake warnings",
            "",
            "Files marked `transcription-required`, `pdf-extractor-required`, or `unsupported` "
            "must be processed by a capable runtime before their content can be treated as read.",
            "Derived office-document text does not preserve images or layout; inspect the original "
            "when visual arrangement, diagrams, equations, speaker notes or exact wording matter.",
            "Exact duplicates must not be ingested twice.",
            "",
        ]
    )
    return "\n".join(lines)
