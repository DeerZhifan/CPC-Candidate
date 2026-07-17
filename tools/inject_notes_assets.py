#!/usr/bin/env python3
"""Idempotently attach shared CSS and JS to all numbered chapter pages."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = '<link rel="stylesheet" href="../shared/notes-enhance.css">'
JS = '<script src="../shared/notes-enhance.js"></script>'


def main() -> None:
    changed = 0
    for path in sorted((ROOT / "notes").glob("* /[0-9][0-9]-*.html".replace(" ", ""))):
        html = path.read_text(encoding="utf-8")
        updated = html
        if CSS not in updated:
            updated = updated.replace("</head>", f"{CSS}\n</head>", 1)
        if JS not in updated:
            updated = updated.replace("</body>", f"{JS}\n</body>", 1)
        if updated != html:
            path.write_text(updated, encoding="utf-8", newline="")
            changed += 1
            print(path.relative_to(ROOT))
    print(f"updated={changed}")


if __name__ == "__main__":
    main()
