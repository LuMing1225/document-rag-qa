# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
from backend.parser.pdf_parser import PDFParser
p = PDFParser()
r = p.parse(r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf", "test")
cols = Counter(str(rg.column) for rg in r.layout_regions)
print("column distribution:", dict(cols))
print()
for rg in r.layout_regions[:8]:
    print(f"  type={rg.type}, column={rg.column}, page={rg.page_number}, bbox={[round(x,1) for x in rg.bbox]}")
print()
# Check chunks column
ccols = Counter(str(c.column) for c in r.chunks)
print("chunk column distribution:", dict(ccols))
