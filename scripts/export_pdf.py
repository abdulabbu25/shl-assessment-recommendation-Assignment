import argparse
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=Path("docs/solution.md"))
    ap.add_argument("--out", type=Path, default=Path("docs/solution.pdf"))
    args = ap.parse_args()

    text = args.src.read_text(encoding="utf-8")
    # Very light markdown handling: treat lines as paragraphs
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    title = styles["Title"]

    story = []
    first = True
    for line in text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue
        style = title if (first and line.startswith("#")) else normal
        story.append(Paragraph(line.replace("#", "").strip(), style))
        first = False
        story.append(Spacer(1, 6))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(args.out), pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    doc.build(story)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
