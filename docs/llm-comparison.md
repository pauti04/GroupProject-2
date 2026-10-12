# LLM Comparison

> **Status:** Run on 2026-10-12 against Groq. Results below are from real runs;
> see the notes on free-tier rate limits, which capped how complete the
> quantitative table could be. Owner: Member B.
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

Headline: **`gpt-oss-120b` completed both tasks; `gpt-oss-20b` completed
neither.** The free Groq tier then throttled further runs (see §5), so some
efficiency numbers below are marked n/a — `gpt-oss-20b` emits run stats only on
successful completion, and its runs failed.

### Per-task breakdown

| Model | Task | Result | Steps | Tool calls | Tool errors | Tokens | Time (s) |
|---|---|---|---|---|---|---|---|
| gpt-oss-120b | bugfix | ✅ pass | 5 | 4 | 1 | 17,464 | 82 |
| gpt-oss-120b | feature | ✅ pass | n/a¹ | n/a¹ | n/a¹ | n/a¹ | 135 |
| gpt-oss-20b | bugfix | ❌ fail | n/a² | n/a² | n/a² | n/a² | 300 (timeout) |
| gpt-oss-20b | feature | ❌ fail | n/a² | n/a² | n/a² | n/a² | 156 |

| Model | Tasks passed |
|---|---|
| gpt-oss-120b | **2 / 2** |
| gpt-oss-20b | **0 / 2** |

¹ The edit was correct and `pytest` passed (4/4), but the run ended on a provider
error on a *later* tool call before stats were written. The `agent.py` retry fix
(§4) addresses that failure mode; a clean re-run would record full stats.

² Golu writes a stats line only when a task finishes; both `gpt-oss-20b` runs
failed, so step/token counts were not recorded. The failure modes are described
below.

### How each run behaved

- **gpt-oss-120b — bugfix (pass):** read the file, made a focused edit to both
  buggy functions, ran `pytest`, saw 3/3 pass, summarized. One tool error along
  the way (a `read_text_file` call it recovered from).
- **gpt-oss-120b — feature (pass):** implemented `median()` correctly (4/4 tests
  pass), then issued one more tool call whose arguments the provider could not
  parse, which ended the run post-success.
- **gpt-oss-20b — bugfix (fail):** looped without converging until it hit the
  time/step cap; the tests were still failing at the end (`2 failed, 1 passed`).
- **gpt-oss-20b — feature (fail):** emitted malformed tool-call JSON and left
  `stats.py` in a state that did not even import (`pytest` collection error).

## 4. Analysis

**Capability gap.** On identical tasks, prompts, tools, and harness, the only
variable was model size, and the outcome was stark: the 120B model solved both
tasks, the 20B model solved neither. The gap is not about "knowing" how to fix a
bug or write a median — both are trivial problems — it is about **driving an
agentic loop**: planning a short sequence of tool calls, reading results, and
stopping when done.

**Tool-calling reliability is the differentiator.** Every `gpt-oss-20b` failure
was a *mechanics* failure, not a reasoning one:
- it emitted `null` for optional parameters it didn't need (fixed by widening the
  schema — see below),
- it called `read_text_file` with `head` *and* `tail` together (contradictory),
- it produced tool-call arguments that weren't valid JSON,
- and on the bugfix it never converged, looping until the cap.

The 120B model made the occasional tool error too, but recovered and finished.
This matches the common finding that small models are usable for chat but
unreliable at the *structured, multi-step tool use* an autonomous agent needs.

**Robustness fixes made during this comparison (design decisions).** Two changes
were needed so the loop degrades gracefully instead of aborting on a single bad
tool call — both help every model, the small one most:
1. *Nullable optional parameters* (`golu/tools/registry.py`): optional scalar
   tool parameters are widened to also accept `null`, so a model's stray
   `{"head": null}` is accepted instead of being rejected by Groq's strict
   validator and failing the whole step.
2. *Retry on a rejected tool call* (`golu/agent.py`): when the provider rejects a
   malformed/unparseable tool call, Golu asks the model to re-emit valid
   arguments and retries once, rather than crashing the task.

**Efficiency / cost.** Where we have numbers, the 120B model was efficient:
bugfix in 5 steps / 4 tool calls / ~17k tokens. The 20B model's apparent
"cheapness" per token is misleading — it completed **zero** tasks, so its real
cost per *completed* task is unbounded. For agentic coding, a model that reliably
finishes in a few steps beats a cheaper model that loops or fails.

## 5. Threats to validity / notes

- **Free-tier rate limits capped the full matrix.** Groq's free tier limits
  `gpt-oss-120b` to **8,000 tokens/minute** — a single agentic request (file
  contents + ~19 tool schemas + history) can exceed that on its own, so repeated
  runs `429`. `gpt-oss-20b` is limited to **200,000 tokens/day**, which a handful
  of runs exhausted. A later attempt to re-run the full 2×2 returned `429`
  rate-limit errors on every cell. The per-task results above are from runs
  captured before the limits bit. **This is itself a finding:** the free tier is
  not practical for sustained agentic coding on the larger model; a paid tier or
  a local Ollama model is needed for a larger benchmark.
- **One run per cell.** Budget did not allow repeating each cell 2-3 times, so
  treat the efficiency numbers as indicative, not averaged. Temperature is fixed
  at 0 (`GOLU_TEMPERATURE`) to reduce variance.
- **Stats only on success.** Golu records a stats line only when a task
  completes, so failed `gpt-oss-20b` runs have no step/token counts; their
  behavior is described qualitatively instead.
- **Tasks are small by design** — "fix a bug" and "implement from a spec" — so
  the comparison is quick and repeatable and maps to the two most common
  coding-assistant jobs.

### Reproducing / extending

Once a higher tier or local model is available, a clean full table is one command
(the harness, fixes, and aggregator are all in place):

```bash
python -m benchmarks.run_comparison \
    --models groq:openai/gpt-oss-120b groq:openai/gpt-oss-20b ollama:qwen2.5-coder:7b \
    --out benchmarks/results.jsonl
python -m benchmarks.aggregate benchmarks/results.jsonl
```
