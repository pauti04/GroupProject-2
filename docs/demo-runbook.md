# Demo Video Runbook

> Owner: Member B. A step-by-step script for recording the demo required by the
> submission: **two non-trivial tasks** with **all three MCP servers visibly
> invoked** (filesystem, our RAG server `golu-docs`, and the external server
> `context7`).
>
> Target length: 4-6 minutes. Record at a readable font size.

## What the rubric needs (checklist)

- [ ] Agent completes **two non-trivial tasks** end to end
- [ ] **Filesystem** MCP server visibly invoked (read/edit/write)
- [ ] **RAG** server (`golu-docs` -> `search_docs`) visibly invoked
- [ ] **External** server (`context7`) visibly invoked
- [ ] Tool calls are visible on screen, and a confirmation prompt is shown at least once

Task 1 covers filesystem + shell. Task 2 covers the RAG server + external docs +
a file write. Together they hit all three servers.

## Prerequisites (set up before recording)

1. `pip install -r requirements.txt` and `pip install pytest`
2. `.env` with `GROQ_API_KEY` set (the demo uses Groq so it's fast and reliable on camera)
3. **Node** installed (the filesystem server starts with `npx`)
4. **Ollama** running, for the RAG server's embeddings, and the index built once:
   ```bash
   ollama pull nomic-embed-text
   git clone --depth 1 --filter=blob:none --sparse https://github.com/langchain-ai/docs rag_server/data/langchain-docs
   git -C rag_server/data/langchain-docs sparse-checkout set src/oss/langchain
   python -m rag_server.ingest
   ```
5. A throwaway scratch folder to act on so edits don't touch the repo:
   ```bash
   mkdir demo-scratch && cp benchmarks/fixtures/task1_bugfix/* demo-scratch/
   ```

Verify the banner shows **all three servers green** before you hit record:
```bash
python -m golu --provider groq --project demo-scratch
```
If `golu-docs` or `context7` is red, fix it first (see README troubleshooting) —
the whole point of the demo is showing them working.

## Recording

### Intro (~20s)
- Show the banner. Point out: provider/model, confirm mode, and the **mcp** rows —
  `filesystem`, `golu-docs`, `context7` all green with their tool counts.
- One line: "Golu is an autonomous CLI coding agent; everything it does is a tool
  call to a local tool or an MCP server."

### Task 1 — Fix failing tests (confirm mode) — filesystem + shell (~90s)

At the `golu ❯` prompt:

```
fix the failing tests in calc.py; run pytest to confirm
```

Narrate as the tool calls appear:
- `list_directory` / `read_text_file` -> **filesystem server** (read-only, no prompt)
- `edit_file` -> filesystem server; **confirmation prompt appears** — say "in confirm
  mode Golu asks before changing anything", then approve with `y`
- `run_shell("python -m pytest")` -> **local tool**; approve; show "tests passed"
- Golu's final summary of what it changed

This checks: two-way filesystem use + shell + a visible confirmation.

### Task 2 — Write code using library docs (auto mode) — RAG + external + filesystem (~2m)

Switch to auto mode so it flows on camera:
```
/mode auto
```
Then:
```
create retriever.py in this folder: use a LangChain Chroma vector store as a
retriever and expose a function search(query) that returns the top 3 documents.
Look up the current LangChain API before writing the code.
```

Narrate as they appear:
- `search_docs("LangChain Chroma retriever")` -> **our RAG server `golu-docs`** —
  pause here: "this is our custom RAG MCP server doing fusion retrieval (BM25 +
  vector) over the LangChain docs we indexed." Show the retrieved snippets.
- a `context7` docs lookup -> **external MCP server** — "and this is the external
  server pulling the current public API, so the code isn't written against a
  stale memory of the library."
- `write_file("retriever.py", ...)` -> **filesystem server** (auto mode: runs
  without a prompt; the new content is shown in a panel)
- Final summary listing the doc sources used

This checks: RAG server + external server + a file write, all visible.

### Wrap (~20s)
- `/tools` to show every loaded tool grouped by server (filesystem, golu-docs,
  context7, local) — reinforces the "multiple MCP servers loaded dynamically" point.
- One closing line on provider abstraction: `/model` can switch between Groq and a
  local Ollama model with no other change.

## Tips

- Keep `GOLU_MAX_STEPS` at the default; if a task stalls on camera, Ctrl+C stops
  the current task without killing the session, then retry.
- Record each task as its own take and stitch them; a clean banner at the start of
  each take makes it obvious the servers are connected.
- If Groq rate-limits mid-take, wait a few seconds and retry, or switch to the
  other model with `/model groq openai/gpt-oss-20b`.
