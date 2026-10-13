"""Turn a benchmark results file into a comparison table for the report.

Reads the JSON-lines file written by run_comparison.py and prints:
  1. a per-model summary (success rate, avg steps / tool calls / errors /
     tokens / time over the tasks),
  2. a per-task breakdown so you can see where a model struggled.

Output is Markdown, ready to paste into docs/llm-comparison.md or the PDF.

    python -m benchmarks.aggregate benchmarks/results.jsonl
    python -m benchmarks.aggregate benchmarks/results.jsonl --md > table.md
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def _load(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Results file not found: {path}")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    if not records:
        raise SystemExit(f"No records in {path}")
    return records


def _stat(rec: dict, key: str, default=0):
    return (rec.get("stats") or {}).get(key, default) or default


def _fmt(value: float) -> str:
    """1 decimal place, but drop a trailing .0 for whole numbers."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def summarize(records: list[dict]) -> str:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        model_key = f"{rec.get('provider', '?')}:{rec.get('model', '?')}"
        by_model[model_key].append(rec)

    out: list[str] = []

    # --- Per-model summary -------------------------------------------------
    out.append("### Per-model summary\n")
    headers = ["Model", "Success", "Avg steps", "Avg tool calls",
               "Avg tool errors", "Avg tokens", "Avg time (s)"]
    rows = []
    for model_key, recs in sorted(by_model.items()):
        n = len(recs)
        passed = sum(1 for r in recs if r.get("success"))
        avg_steps = mean(_stat(r, "steps") for r in recs)
        avg_calls = mean(_stat(r, "tool_calls") for r in recs)
        avg_errors = mean(_stat(r, "tool_errors") for r in recs)
        avg_tokens = mean(_stat(r, "input_tokens") + _stat(r, "output_tokens") for r in recs)
        avg_time = mean(r.get("wall_seconds", _stat(r, "seconds")) for r in recs)
        rows.append([
            model_key,
            f"{passed}/{n} ({100 * passed / n:.0f}%)",
            _fmt(avg_steps), _fmt(avg_calls), _fmt(avg_errors),
            _fmt(avg_tokens), _fmt(avg_time),
        ])
    out.append(_table(headers, rows))

    # --- Per-task breakdown ------------------------------------------------
    out.append("\n### Per-task breakdown\n")
    headers = ["Model", "Task", "Result", "Steps", "Tool calls", "Errors", "Tokens", "Time (s)"]
    rows = []
    for model_key, recs in sorted(by_model.items()):
        for r in sorted(recs, key=lambda x: x.get("task_id", "")):
            tokens = _stat(r, "input_tokens") + _stat(r, "output_tokens")
            rows.append([
                model_key,
                r.get("task_id", "?"),
                "pass" if r.get("success") else "FAIL",
                str(_stat(r, "steps")),
                str(_stat(r, "tool_calls")),
                str(_stat(r, "tool_errors")),
                str(tokens),
                _fmt(r.get("wall_seconds", _stat(r, "seconds"))),
            ])
    out.append(_table(headers, rows))

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate benchmark results into a Markdown table.")
    parser.add_argument("results", type=Path, help="JSONL results file from run_comparison.py")
    parser.add_argument("--md", action="store_true", help="print only the Markdown (no header line)")
    args = parser.parse_args(argv)

    records = _load(args.results)
    if not args.md:
        print(f"# LLM comparison - {len(records)} runs from {args.results.name}\n")
    print(summarize(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
