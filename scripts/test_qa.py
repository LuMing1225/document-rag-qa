# -*- coding: utf-8 -*-
import requests, sys
sys.stdout.reconfigure(encoding="utf-8")

resp = requests.post("http://localhost:8563/api/chat/query", json={
    "question": "婴儿黄疸达到多少数值需要采取光疗，同时应如何调整喂养量？",
    "kb_id": "kb_20261001_173158_115b5e",
    "top_k": 5
}, timeout=180)
data = resp.json()
print("=== ANSWER ===")
print(data.get("answer", ""))
print()
chunks = data.get("retrieved_chunks", [])
print(f"=== RETRIEVED {len(chunks)} chunks ===")
for i, c in enumerate(chunks[:3]):
    print(f"--- #{i+1} final={c.get('score')} dense={c.get('dense_score')} rerank={c.get('rerank_score')} pages={c.get('page_numbers')} ---")
    print(c.get("text", "")[:400])
    print()
