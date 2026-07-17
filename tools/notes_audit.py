#!/usr/bin/env python3
"""OCR the scanned four-color notes and audit HTML knowledge coverage.

The PDFs in this repository are image-only.  This tool keeps OCR output under
``tmp/notes-audit`` so the expensive step can be resumed, then builds a
chapter-level report that points reviewers at likely omissions.  OCR is
evidence for review, not an authority for automatically rewriting study notes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "tmp" / "notes-audit"


@dataclass(frozen=True)
class Subject:
    key: str
    directory: Path
    pdf_name: str

    @property
    def pdf(self) -> Path:
        return self.directory / self.pdf_name

    @property
    def cache(self) -> Path:
        return CACHE_ROOT / self.key


SUBJECTS = {
    "law-fort": Subject("law-fort", ROOT / "notes" / "law-fort", "一建法规四色笔记.pdf"),
    "eco-war": Subject("eco-war", ROOT / "notes" / "eco-war", "一建经济四色笔记.pdf"),
    "cmd-core": Subject("cmd-core", ROOT / "notes" / "cmd-core", "一建项目管理四色笔记.pdf"),
}


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script", "svg"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "svg"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


class TagBalanceParser(HTMLParser):
    """Catch malformed nesting that simple opening/closing counts miss."""

    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.VOID_TAGS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        line = self.getpos()[0]
        if not self.stack:
            self.errors.append(f"line {line}: unexpected </{tag}>")
            return
        open_tag, open_line = self.stack[-1]
        if open_tag != tag:
            self.errors.append(
                f"line {line}: </{tag}> closes <{open_tag}> from line {open_line}"
            )
            return
        self.stack.pop()


def visible_text(path: Path) -> str:
    parser = VisibleTextParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return "\n".join(parser.parts)


def normalize(text: str) -> str:
    """Normalize for fuzzy Chinese text comparison without losing digits."""
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff%]+", "", text).lower()


def selected_subjects(value: str) -> list[Subject]:
    if value == "all":
        return list(SUBJECTS.values())
    return [SUBJECTS[value]]


def ocr_subject(subject: Subject, scale: float, force: bool) -> None:
    try:
        import fitz
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise SystemExit(
            "Missing OCR dependencies. Install with: "
            "python -m pip install pymupdf rapidocr onnxruntime"
        ) from exc

    if not subject.pdf.exists():
        raise SystemExit(f"PDF not found: {subject.pdf}")

    pages_dir = subject.cache / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(subject.pdf)
    engine = RapidOCR()
    print(f"[{subject.key}] {len(document)} pages, scale={scale}", flush=True)

    for index, page in enumerate(document):
        target = pages_dir / f"{index + 1:03d}.json"
        if target.exists() and not force:
            print(f"[{subject.key}] {index + 1:03d}/{len(document)} cached", flush=True)
            continue

        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        result = engine(pixmap.tobytes("png"))
        lines: list[dict[str, object]] = []
        if result.txts:
            for box, text, score in zip(result.boxes, result.txts, result.scores):
                lines.append(
                    {
                        "text": text,
                        "score": round(float(score), 5),
                        "box": [[round(float(x), 1), round(float(y), 1)] for x, y in box],
                    }
                )
        payload = {
            "subject": subject.key,
            "pdf": subject.pdf.name,
            "page": index + 1,
            "scale": scale,
            "width": pixmap.width,
            "height": pixmap.height,
            "lines": lines,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(
            f"[{subject.key}] {index + 1:03d}/{len(document)} "
            f"lines={len(lines):03d}",
            flush=True,
        )

    combined = subject.cache / f"{subject.key}-ocr.txt"
    with combined.open("w", encoding="utf-8") as stream:
        for page_file in sorted(pages_dir.glob("*.json")):
            page = json.loads(page_file.read_text(encoding="utf-8"))
            stream.write(f"\n===== PDF PAGE {page['page']:03d} =====\n")
            stream.write("\n".join(line["text"] for line in page["lines"]))
            stream.write("\n")
    print(f"[{subject.key}] complete: {combined}", flush=True)


def load_pages(subject: Subject) -> list[dict[str, object]]:
    pages_dir = subject.cache / "pages"
    pages = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pages_dir.glob("*.json"))]
    if not pages:
        raise SystemExit(f"No OCR cache for {subject.key}. Run the ocr command first.")
    actual_numbers = [int(page["page"]) for page in pages]
    if actual_numbers != list(range(1, len(pages) + 1)):
        raise SystemExit(f"OCR cache for {subject.key} has missing or duplicate page numbers.")
    return pages


def page_text(page: dict[str, object]) -> str:
    return "\n".join(str(line["text"]) for line in page["lines"])


def chapter_files(subject: Subject) -> list[Path]:
    return sorted(p for p in subject.directory.glob("[0-9][0-9]-*.html") if not p.name.startswith("00-"))


def chapter_title(path: Path) -> str:
    text = visible_text(path)
    match = re.search(r"第\s*\d+\s*章[^\n]*", text)
    return match.group(0).strip() if match else path.stem[3:]


def locate_chapters(files: Sequence[Path], pages: Sequence[dict[str, object]]) -> list[int]:
    starts: list[int] = []
    # The first 8-10 PDF pages are covers, preface and contents.  A chapter name
    # appearing there must not be mistaken for the chapter's actual first page.
    cursor = min(8, max(0, len(pages) - 1))
    normalized_pages = [normalize(page_text(page)) for page in pages]
    titles = [normalize(path.stem[3:]) for path in files]
    title_hits = [sum(1 for title in titles if title and title in page) for page in normalized_pages]
    for path in files:
        chapter_number = int(path.name[:2])
        section_marker = re.compile(
            rf"(?m)^\s*{chapter_number}\s*[.．]\s*1\s*[.．]\s*1(?:\D|$)"
        )
        # The first N.1.1 heading is a more reliable boundary than the decorative
        # chapter title: some openers place the title at the bottom of the
        # previous page, while contents pages repeat every chapter name.  Using
        # the first item also keeps a shared transition page with the chapter
        # whose actual study content occupies it.
        marker_index = next(
            (
                index
                for index in range(cursor, len(pages))
                if section_marker.search(page_text(pages[index]))
            ),
            None,
        )
        if marker_index is not None:
            starts.append(marker_index)
            cursor = min(marker_index + 1, len(pages) - 1)
            continue

        title = normalize(chapter_title(path))
        short_title = normalize(path.stem[3:])
        best: tuple[float, int] = (0.0, cursor)
        for index in range(cursor, len(pages)):
            page = normalized_pages[index]
            # Actual chapter openers put the title near the top and normally do
            # not list several other chapter titles (unlike contents pages).
            head = page[: max(260, len(short_title) * 12)]
            exact = (title and title in head) or (short_title and short_title in head)
            if exact and title_hits[index] <= 2:
                best = (1.0, index)
                break
            score = SequenceMatcher(None, short_title, head).ratio()
            score -= max(0, title_hits[index] - 1) * 0.08
            if score > best[0]:
                best = (score, index)
        starts.append(best[1])
        cursor = min(best[1] + 1, len(pages) - 1)
    return starts


def useful_ocr_lines(pages: Iterable[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for page in pages:
        for item in page["lines"]:
            line = str(item["text"]).strip()
            norm = normalize(line)
            if len(norm) < 8:
                continue
            if re.fullmatch(r"第?\d+页?", line):
                continue
            result.append(line)
    return result


def missing_numbered_subsections(
    chapter_number: int,
    pages: Iterable[dict[str, object]],
    html_normalized: str,
) -> list[str]:
    """Return OCR item headings such as 3.2.4 that are absent from HTML."""
    heading = re.compile(
        rf"^{chapter_number}\s*[.．]\s*(\d+)\s*[.．]\s*(\d+)\s*(.*)"
    )
    seen: list[tuple[str, str]] = []
    for page in pages:
        for item in page["lines"]:
            text = str(item["text"]).strip()
            match = heading.match(text)
            if not match:
                continue
            number = f"{chapter_number}.{match.group(1)}.{match.group(2)}"
            title = re.sub(r"[（(].*$", "", match.group(3)).strip()
            key = (number, title)
            if key not in seen:
                seen.append(key)

    missing: list[str] = []
    for number, title in seen:
        title_normalized = normalize(title)
        if normalize(number) in html_normalized:
            continue
        if title_normalized and title_normalized in html_normalized:
            continue
        missing.append(f"{number} {title}".strip())
    return missing


def line_covered(line: str, html_norm: str) -> bool:
    candidate = normalize(line)
    if not candidate:
        return True
    if candidate in html_norm:
        return True
    # Long OCR lines often wrap differently in HTML.  Matching either end is a
    # strong, cheap signal while still surfacing genuinely absent statements.
    span = min(16, max(8, len(candidate) // 3))
    if candidate[:span] in html_norm and candidate[-span:] in html_norm:
        return True
    gram_size = 4
    if len(candidate) >= gram_size * 2:
        grams = {candidate[index : index + gram_size] for index in range(len(candidate) - gram_size + 1)}
        hit_ratio = sum(gram in html_norm for gram in grams) / len(grams)
        if hit_ratio >= 0.68:
            return True
    return False


def report_subject(subject: Subject) -> Path:
    pages = load_pages(subject)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("pypdf is required to verify OCR cache completeness.") from exc
    expected_pages = len(PdfReader(str(subject.pdf)).pages)
    if len(pages) != expected_pages:
        raise SystemExit(
            f"OCR cache for {subject.key} is incomplete: {len(pages)}/{expected_pages} pages."
        )
    files = chapter_files(subject)
    starts = locate_chapters(files, pages)
    report_dir = subject.cache / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    target = report_dir / "coverage.md"

    rows: list[str] = []
    detail: list[str] = []
    for idx, path in enumerate(files):
        start = starts[idx]
        end = starts[idx + 1] if idx + 1 < len(starts) else len(pages)
        chapter_pages = pages[start:end]
        lines = useful_ocr_lines(chapter_pages)
        html = visible_text(path)
        html_norm = normalize(html)
        missing = [line for line in lines if not line_covered(line, html_norm)]
        numbered_gaps = missing_numbered_subsections(
            int(path.name[:2]), chapter_pages, html_norm
        )
        covered = len(lines) - len(missing)
        ratio = covered / len(lines) if lines else 0.0
        rows.append(
            f"| {path.name} | {start + 1}-{end} | {len(lines)} | "
            f"{covered} | {ratio:.1%} | {len(missing)} |"
        )
        detail.append(f"\n## {path.name}\n")
        detail.append(
            f"PDF 页 {start + 1}-{end}；OCR 长句 {len(lines)}；字面覆盖 {ratio:.1%}。\n"
        )
        detail.append(
            "编号知识点检查："
            + ("未发现整段缺号。\n" if not numbered_gaps else "；".join(numbered_gaps) + "\n")
        )
        detail.append("以下是候选遗漏，须对照原页人工确认；同义改写也会被列出。\n")
        for line in missing[:80]:
            detail.append(f"- {line}\n")
        if len(missing) > 80:
            detail.append(f"- ...另有 {len(missing) - 80} 条，见 OCR 分页缓存。\n")

    header = [
        f"# {subject.key} 四色笔记 HTML 覆盖审计\n",
        "\n> 本报告用于定位候选遗漏，不代表自动判定。表格/换行/OCR误差和HTML同义改写会降低字面覆盖率。\n",
        "\n| HTML 章节 | PDF 实际页 | OCR 长句 | 字面命中 | 字面覆盖率 | 候选遗漏 |\n",
        "|---|---:|---:|---:|---:|---:|\n",
        *[row + "\n" for row in rows],
    ]
    target.write_text("".join(header + detail), encoding="utf-8")
    print(target)
    return target


def inventory_subject(subject: Subject) -> None:
    class_names = [
        "table",
        "trap",
        "ex",
        "flow",
        "timeline",
        "compare-grid",
        "formula-card",
        "memory-chain",
        "decision-tree",
        "cycle",
        "visual-note",
    ]
    print("file\titems\t" + "\t".join(class_names))
    for path in chapter_files(subject):
        html = path.read_text(encoding="utf-8")
        values = [
            len(re.findall(r'<details class="item"', html)),
            *[len(re.findall(fr'(?:class="[^"]*\b{name}\b|<{name}\b)', html)) for name in class_names],
        ]
        print(path.name + "\t" + "\t".join(map(str, values)))


def validate_subject(subject: Subject) -> list[str]:
    errors: list[str] = []
    numbered = sorted(subject.directory.glob("[0-9][0-9]-*.html"))
    for path in numbered:
        html = path.read_text(encoding="utf-8")
        if html.count('../shared/notes-enhance.css') != 1:
            errors.append(f"{path.relative_to(ROOT)}: shared CSS must be referenced once")
        if html.count('../shared/notes-enhance.js') != 1:
            errors.append(f"{path.relative_to(ROOT)}: shared JS must be referenced once")
        if html.count("<details") != html.count("</details>"):
            errors.append(f"{path.relative_to(ROOT)}: unbalanced details elements")
        balance = TagBalanceParser()
        balance.feed(html)
        if balance.errors:
            errors.append(f"{path.relative_to(ROOT)}: {balance.errors[0]}")
        elif balance.stack:
            tag, line = balance.stack[-1]
            errors.append(f"{path.relative_to(ROOT)}: unclosed <{tag}> from line {line}")
        if re.search(r'<div class="flow">\s*<div(?! class="step")', html):
            errors.append(f"{path.relative_to(ROOT)}: flow children must use class=\"step\"")
        for attr, value in re.findall(r'\b(href|src)="([^"]+)"', html):
            if value.startswith(("#", "http://", "https://", "data:", "javascript:")):
                continue
            clean = value.split("#", 1)[0].split("?", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{path.relative_to(ROOT)}: missing {attr} target {value}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ocr_parser = subparsers.add_parser("ocr", help="OCR PDF pages into a resumable cache")
    ocr_parser.add_argument("--subject", choices=["all", *SUBJECTS], default="all")
    ocr_parser.add_argument("--scale", type=float, default=1.35)
    ocr_parser.add_argument("--force", action="store_true")

    report_parser = subparsers.add_parser("report", help="Build candidate omission reports")
    report_parser.add_argument("--subject", choices=["all", *SUBJECTS], default="all")

    inventory_parser = subparsers.add_parser("inventory", help="Count visual forms in chapter HTML")
    inventory_parser.add_argument("--subject", choices=["all", *SUBJECTS], default="all")

    validate_parser = subparsers.add_parser("validate", help="Validate shared assets, links and details structure")
    validate_parser.add_argument("--subject", choices=["all", *SUBJECTS], default="all")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    subjects = selected_subjects(args.subject)
    if args.command == "ocr":
        for subject in subjects:
            ocr_subject(subject, args.scale, args.force)
    elif args.command == "report":
        for subject in subjects:
            report_subject(subject)
    elif args.command == "inventory":
        for subject in subjects:
            inventory_subject(subject)
    elif args.command == "validate":
        errors = [error for subject in subjects for error in validate_subject(subject)]
        if errors:
            print("\n".join(errors))
            return 1
        print(f"validated_subjects={len(subjects)} errors=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
