#!/usr/bin/env python3
import os
import sys

# Ensure repository root is importable (for 'ehr' package)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ehr.builder import build_ehr_index


def main():
    # Hardcoded build using the sample patient history in this repo
    input_file = os.path.join(REPO_ROOT, "ehr", "patient_history.txt")
    output_dir = os.path.join(REPO_ROOT, "ehr_index")

    os.makedirs(output_dir, exist_ok=True)
    out = build_ehr_index(
        input_path=input_file,
        output_dir=output_dir,
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        chunk_tokens=256,
        overlap_tokens=32,
    )
    print(f"Index built at: {out}")


if __name__ == "__main__":
    main()
