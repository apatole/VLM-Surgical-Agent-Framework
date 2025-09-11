#!/usr/bin/env python3
import argparse
import os
import sys
import json
import yaml

# Ensure repository root is importable (for 'agents' and 'ehr' packages)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from utils.response_handler import ResponseHandler
from agents.ehr_agent import EHRAgent
from ehr.store import EHRVectorStore


def main():
    p = argparse.ArgumentParser(description="Query the EHR vector store using EHRAgent")
    p.add_argument("--config", default="configs/ehr_agent.yaml", help="Path to EHRAgent YAML config")
    p.add_argument("--question", required=True, help="User question")
    p.add_argument("--dry-run-retrieval", action="store_true", help="Only run retrieval, skip LLM call")
    p.add_argument("--top-k", type=int, default=None, help="Override retrieval_top_k from config")
    args = p.parse_args()

    # Load agent config and global llm url to provide clearer progress messages
    with open(args.config, "r") as f:
        agent_cfg = yaml.safe_load(f) or {}
    cfg_dir = os.path.dirname(os.path.abspath(args.config))
    global_cfg_path = os.path.join(cfg_dir, "global.yaml")
    llm_url = os.environ.get("VLLM_URL")
    if not llm_url and os.path.isfile(global_cfg_path):
        with open(global_cfg_path, "r") as gf:
            gcfg = yaml.safe_load(gf) or {}
            llm_url = gcfg.get("llm_url")
    if not llm_url:
        llm_url = "http://127.0.0.1:8000/v1"

    ehr_index_dir = agent_cfg.get("ehr_index_dir", "ehr_index")
    emb_model = agent_cfg.get("embedding_model_name", "sentence-transformers/all-MiniLM-L6-v2")
    top_k = args.top_k if args.top_k is not None else int(agent_cfg.get("retrieval_top_k", 5))

    if args.dry_run_retrieval:
        print(f"[ehr_query] Dry-run retrieval only. Loading index from: {ehr_index_dir}")
        store = EHRVectorStore.from_dir(ehr_index_dir, emb_model)
        hits = store.query(args.question, top_k=top_k)
        print(f"[ehr_query] Retrieved {len(hits)} chunk(s):\n")
        for i, h in enumerate(hits, 1):
            src = h.metadata.get("source", "unknown")
            ck = h.metadata.get("chunk_index", "?")
            print(f"[{i}] score={h.score:.3f} source={src} chunk={ck}")
            print(h.text.strip()[:400].replace("\n\n", "\n"))
            print("---")
        return

    print(f"[ehr_query] Connecting to vLLM at {llm_url} …")
    print(f"[ehr_query] Using EHR index: {ehr_index_dir} (embedder: {emb_model}, top_k={top_k})")

    rh = ResponseHandler()
    try:
        agent = EHRAgent(args.config, rh)
    except Exception as e:
        print(f"[ehr_query] Failed to initialize EHRAgent: {e}")
        sys.exit(1)

    out = agent.process_request(args.question, chat_history=[])
    print(out.get("response", ""))


if __name__ == "__main__":
    main()
