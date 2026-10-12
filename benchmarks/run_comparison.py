"""Run the benchmark task set across several models and record the results.

Member B deliverable: the LLM comparison. This orchestrates Golu itself, so
whatever the agentic loop actually does end to end is what gets measured.

For each (model, task) pair it:
  1. copies the task fixture to a fresh temp folder (so every run starts clean),
  2. runs `python -m golu --provider ... --model ... --mode auto -p <prompt>
     --project <tmp> --stats-file <tmp stats>`,
  3. reads back the one stats line Golu appended (steps, tool calls, errors,
     tokens, time),
  4. runs the task's verify command to decide success objectively,
  5. appends one merged JSON record to the results file.

Then run `python -m benchmarks.aggregate <results file>` to get the table.

Models are given as `provider:model`, e.g.:

    python -m benchmarks.run_comparison \
        --models groq:openai/gpt-oss-120b groq:openai/gpt-oss-20b \
        --out benchmarks/results.jsonl

Requirements for a real run: a working Golu (API key in .env for cloud
providers, or Ollama running), Node for the filesystem MCP server, and pytest
available on PATH for the verify step. No RAG index is needed — these tasks
only use the filesystem server and run_shell, and Golu skips servers that fail
to start.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from benchmarks.tasks import TASKS, Task, get_task

REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_model(spec: str) -> tuple[str, str]:
    """'groq:openai/gpt-oss-120b' -> ('groq', 'openai/gpt-oss-120b')."""
    if ":" not in spec:
        raise SystemExit(f"Model '{spec}' must be in provider:model form, e.g. groq:openai/gpt-oss-120b")
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


def _run_golu(provider: str, model: str, task: Task, project: Path,
              stats_file: Path, max_steps: int, timeout: int) -> dict:
    """Run Golu once on a task. Returns the stats dict it recorded (or an error record)."""
    cmd = [
        sys.executable, "-m", "golu",
        "--provider", provider,
        "--model", model,
        "--mode", "auto",
        "--project", str(project),
        "--max-steps", str(max_steps),
        "--stats-file", str(stats_file),
        "-p", task.prompt,
    ]
    # Golu's Rich UI emits Unicode (banner, tool panels). When we capture its
    # output the pipe defaults to the OS encoding (cp1252 on Windows), which
    # makes Rich crash. Force UTF-8 I/O for the child process.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"golu timed out after {timeout}s", "hit_step_limit": True}

    # Golu appends one JSON line per task; read the last line it wrote.
    if stats_file.exists():
        lines = [l for l in stats_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            try:
                return json.loads(lines[-1])
            except json.JSONDecodeError:
                pass
    # No stats line means Golu errored before finishing (e.g. the provider
    # rejected the model's output). Capture both streams so the write-up can
    # report the failure mode.
    return {"error": f"golu produced no stats (exit {proc.returncode})",
            "stdout_tail": (proc.stdout or "")[-800:],
            "stderr_tail": (proc.stderr or "")[-500:]}


def _verify(task: Task, project: Path, timeout: int) -> tuple[bool, str]:
    """Run the task's verify command in the project; True iff it exits 0."""
    try:
        proc = subprocess.run(
            task.verify, cwd=str(project), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f"verify failed to run: {exc}"
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output[-600:]


def run_pair(provider: str, model: str, task: Task, out: Path,
             max_steps: int, agent_timeout: int, verify_timeout: int) -> dict:
    """Run one model on one task and append a merged record to `out`."""
    with tempfile.TemporaryDirectory(prefix=f"golu-bench-{task.id}-") as tmp:
        project = Path(tmp) / task.fixture.name
        shutil.copytree(task.fixture, project)
        stats_path = Path(tmp) / "stats.jsonl"

        started = time.perf_counter()
        stats = _run_golu(provider, model, task, project, stats_path, max_steps, agent_timeout)
        success, verify_output = _verify(task, project, verify_timeout)

    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "task_id": task.id,
        "task_title": task.title,
        "success": success,
        "wall_seconds": round(time.perf_counter() - started, 1),
        "verify_output_tail": verify_output,
        # Everything Golu recorded (steps, tool_calls, tool_errors, tokens, ...):
        "stats": stats,
    }
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the LLM comparison benchmark.")
    parser.add_argument("--models", nargs="+", required=True,
                        help="models as provider:model, e.g. groq:openai/gpt-oss-120b")
    parser.add_argument("--tasks", nargs="*", default=[t.id for t in TASKS],
                        help="task ids to run (default: all)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "results.jsonl")
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--agent-timeout", type=int, default=600,
                        help="seconds before a single Golu run is killed")
    parser.add_argument("--verify-timeout", type=int, default=120)
    args = parser.parse_args(argv)

    models = [_parse_model(m) for m in args.models]
    tasks = [get_task(tid) for tid in args.tasks]
    args.out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(models)} model(s) x {len(tasks)} task(s) -> {args.out}\n")
    for provider, model in models:
        for task in tasks:
            label = f"{provider}:{model}  |  {task.id}"
            print(f">> {label} ...", flush=True)
            rec = run_pair(provider, model, task, args.out,
                           args.max_steps, args.agent_timeout, args.verify_timeout)
            s = rec["stats"]
            status = "PASS" if rec["success"] else "FAIL"
            steps = s.get("steps", "?")
            print(f"   {status}  ({steps} steps, {rec['wall_seconds']}s)\n", flush=True)

    print(f"Done. Aggregate with:\n  python -m benchmarks.aggregate {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
