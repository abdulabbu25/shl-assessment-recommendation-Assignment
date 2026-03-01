from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
import markdown as md
import re
import argparse

def md_to_flow(text: str):
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]
    normal = styles["Normal"]
    flow = []
    lines = text.splitlines()
    buffer = []
    def flush_paragraph():
        if buffer:
            flow.append(Paragraph(" ".join(buffer).strip(), normal))
            flow.append(Spacer(1, 6))
            buffer.clear()
    bullets = []
    for line in lines:
        if line.startswith("# "):
            flush_paragraph()
            flow.append(Paragraph(line[2:].strip(), h1))
            flow.append(Spacer(1, 8))
        elif line.startswith("## "):
            flush_paragraph()
            flow.append(Paragraph(line[3:].strip(), h2))
            flow.append(Spacer(1, 6))
        elif line.startswith("### "):
            flush_paragraph()
            flow.append(Paragraph(line[4:].strip(), h3))
            flow.append(Spacer(1, 4))
        elif line.strip().startswith("- "):
            bullets.append(Paragraph(line.strip()[2:], normal))
        elif line.strip() == "":
            if bullets:
                flow.append(ListFlowable([ListItem(b, leftIndent=12) for b in bullets]))
                flow.append(Spacer(1, 6))
                bullets = []
            else:
                flush_paragraph()
        else:
            buffer.append(line.strip())
    if bullets:
        flow.append(ListFlowable([ListItem(b, leftIndent=12) for b in bullets]))
        flow.append(Spacer(1, 6))
    flush_paragraph()
    return flow

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, default=Path("docs/solution.md"))
    ap.add_argument("--out", type=Path, default=Path("solution.pdf"))
    args = ap.parse_args()

    raw = args.md.read_text(encoding="utf-8")
    flow = md_to_flow(raw)
    doc = SimpleDocTemplate(str(args.out), pagesize=A4, topMargin=36, bottomMargin=36, leftMargin=36, rightMargin=36)
    # Add a soft page break if too long
    # ReportLab will naturally paginate; we just build the story.
    doc.build(flow)
    print(f"Wrote {args.out.resolve()}")

if __name__ == "__main__":
    main()
