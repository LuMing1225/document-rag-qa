# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\shixunXM\工单4\03-长文本版面分析RAG检索系统")
from backend.parser.pdf_parser import PDFParser
p = PDFParser()
r = p.parse(r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf", "test")

# Simulate frontend bbox double-column detection
page_text_x = {}
for rg in r.layout_regions:
    if rg.type not in ("text", "title", "table"):
        continue
    x0, y0, x1, y1 = rg.bbox
    if (x1 - x0) < 280:
        page_text_x.setdefault(rg.page_number, []).append((x0, x1))

for pno, xs in sorted(page_text_x.items()):
    has_left = any(x0 < 290 for x0, x1 in xs)
    has_right = any(x1 > 305 for x0, x1 in xs)
    print(f"Page {pno}: {len(xs)} narrow regions, left={has_left}, right={has_right}, double_col={has_left and has_right}")
    for x0, x1 in xs[:5]:
        print(f"  x=[{x0:.1f}, {x1:.1f}] width={x1-x0:.1f}")
