# LLM Comparison

> **Status:** Harness and methodology complete; results tables are placeholders
> to be filled once the benchmark is run with a live model. Owner: Member B.
>
> This document satisfies the submission requirement: *"A comparison of at
> least two different LLMs on the same coding task and any insights gained."*
> It is written to be lifted straight into the PDF report.

## 1. What we compare and why

Golu is model-agnostic (see `golu/providers.py`): the same agentic loop, tools,
and prompts run against any provider. That lets us hold everything constant and
change only the model, so differences in the results come from the model, not
the harness.

We run **the same coding tasks** through the **full agent** (not a one-shot
prompt) on each model and measure how well and how efficiently each one drives
the loop to a verified result.

### Models

We compare at least two models. Because the team has a Groq API key, the primary
comparison is between two Groq-hosted models of different size/family:

| Role | Model (provider:model) | Why it's here |
|---|---|---|
| Large cloud | `groq:openai/gpt-oss-120b` | Larger model; stronger tool-calling baseline |
| Smaller cloud | `groq:openai/gpt-oss-20b` | Same family, ~6x smaller; tests how a smaller model drives the same loop |

> Model names current as of Oct 2026. Groq retired the Llama 3.x versatile/instant
> models in Aug 2026; `openai/gpt-oss-120b` and `openai/gpt-oss-20b` are the current
> production text models. Confirm your account's live list with
> `GET https://api.groq.com/openai/v1/models` before a run.

*Optional third model:* `ollama:qwen2.5-coder:7b` once Ollama is installed, to add
a local-vs-cloud dimension. The harness takes any number of `provider:model`
entries, so adding it is one more argument.

### Tasks

Two non-trivial, deterministically verifiable coding tasks (defined in
`benchmarks/tasks.py`). These are the same tasks used in the demo video.

| ID | Task | Exercises | Success = |
|---|---|---|---|
| `bugfix` | Find and fix two bugs in `calc.py` so the unit tests pass | filesystem read/edit, `run_shell` (pytest) | `pytest` exits 0 |
| `feature` | Implement `median()` in `stats.py` from a spec + failing tests | filesystem read/write, `run_shell` (pytest) | `pytest` exits 0 |

Each task starts from a fresh copy of its fixture, so no run contaminates
another, and success is decided by an objective verify command, not by reading
the model's own summary.

### Metrics

Recorded per run by Golu's `--stats-file` plus the benchmark's own verify step:

- **Success** — did the verify command pass? (the headline number)
- **Steps** — LLM turns in the agentic loop
- **Tool calls** and **tool errors** — how efficiently/cleanly it used tools
- **Tokens** — input + output (cost/efficiency proxy)
- **Time** — wall-clock seconds per task

## 2. How to reproduce

Requirements: a working Golu (`GROQ_API_KEY` in `.env`), Node (filesystem MCP
server), and `pytest` installed (`pip install pytest`). No RAG index is needed —
these tasks use only the filesystem server and `run_shell`.

```bash
# From the repo root, with the venv active:
python -m benchmarks.run_comparison \
    --models groq:openai/gpt-oss-120b groq:openai/gpt-oss-20b \
    --out benchmarks/results.jsonl

# Build the comparison tables:
python -m benchmarks.aggregate benchmarks/results.jsonl
```

To add the local model later, append `ollama:qwen2.5-coder:7b` to `--models`.

## 3. Results

> Paste the output of `python -m benchmarks.aggregate` here after running.

### Per-model summary

| Model | Success | Avg steps | Avg tool calls | Avg tool errors | Avg tokens | Avg time (s) |
| --- | --- | --- | --- | --- | --- | --- |
| _(fill after run)_ | | | | | | |

### Per-task breakdown

| Model | Task | Result | Steps | Tool calls | Errors | Tokens | Time (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| _(fill after run)_ | | | | | | | |

## 4. Analysis

> Write 2-4 short paragraphs once numbers are in. Prompts to answer:
>
> - **Success:** Did both models complete both tasks? If one failed, *how* did
>   it fail (hit the step limit, looped on a failing command, produced invalid
>   tool-call JSON, edited the wrong file)? Check `verify_output_tail` in
>   `results.jsonl`.
> - **Efficiency:** The large model usually needs fewer steps and fewer tool
>   errors. Quantify it (e.g. "the 8B model used X% more tool calls").
> - **Cost/speed trade-off:** Smaller/cheaper model vs. token and time cost of
>   its extra steps and retries. Is the cheaper model actually cheaper per
>   *completed* task once retries are counted?
> - **Tool calling reliability:** Note whether the smaller model emitted invalid
>   tool arguments (Golu logs "invalid tool arguments" and asks it to retry) or
>   needed the max-steps safety net.

## 5. Threats to validity / notes

- LLM outputs are non-deterministic; temperature is fixed at 0 (`GOLU_TEMPERATURE`)
  to reduce variance, but results can still differ run to run. Consider running
  each pair 2-3 times and reporting the typical outcome.
- Free-tier rate limits can slow or interrupt runs; the harness records a clear
  error record rather than crashing the batch.
- The tasks are small by design so the comparison is quick and repeatable; they
  are representative of "fix a bug" and "implement from a spec", the two most
  common coding-assistant jobs.
