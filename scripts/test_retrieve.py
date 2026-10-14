# -*- coding: utf-8 -*-
import sys, requests
sys.stdout.reconfigure(encoding="utf-8")

kb_id = "kb_20261001_203452_07bd2a"
r = requests.get("http://localhost:8563/api/chat/retrieve",
    params={"question": "婴儿黄疸光疗阈值", "kb_id": kb_id, "top_k": 5, "use_reranker": "false"},
    timeout=60)
data = r.json()
parents = data.get("parents", [])
print(f"Retrieved {len(parents)} parent chunks")
for i, p in enumerate(parents[:2]):
    score = p.get("score")
    pages = p.get("page_numbers")
    text = p.get("text", "")[:150]
    print(f"  #{i+1} score={score} pages={pages}")
    print(f"  text: {text}")
    print()
