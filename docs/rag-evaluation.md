# RAG Evaluation: Fusion Retrieval vs. Vector Search

> **Status:** Run on 2026-10-12 against the local index. Owner: Member C.
>
> This document covers the submission requirement *"any insights gained from
> using your chosen advanced RAG technique"*. It is written to be lifted
> straight into the PDF report. Raw numbers: `docs/rag-eval-results.json`.

## 1. What we built

Golu's custom MCP server, `golu-docs`, exposes one tool, `search_docs`, over the
LangChain Python documentation.

| Stage | What happens | Where |
|---|---|---|
| Load | 55 `.mdx` pages from `langchain-ai/docs` (`src/oss/langchain`); React/JS-only pages excluded | `ingest.py`, `settings.py` |
| Clean + chunk | JSX and JS-only blocks dropped; split by heading into ~1,200-char chunks (200 overlap) without breaking code blocks | `chunking.py` |
| Contextual headers | Each chunk is prefixed with its document title and section path before embedding | `chunking.py` |
| Embed + store | `nomic-embed-text` via Ollama, stored in Chroma (cosine) | `store.py` |
| Retrieve | **Fusion Retrieval** (vector + BM25), returned to the agent with source URLs | `retriever.py`, `server.py` |

The index is built **once** (`python -m rag_server.ingest`): 995 chunks, average
725 characters, 13 MB on disk, about 7 minutes on a laptop CPU. Every later
Golu session opens the same Chroma folder; the BM25 index is rebuilt in memory
from the stored chunks at server start (0.3 s), so nothing is re-embedded.

## 2. The advanced technique: Fusion Retrieval

From [NirDiamant/RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques)
("Fusion Retrieval"):

1. Take the top 40 candidates from **vector search** (meaning) and the top 40
   from **BM25** (exact keywords).
2. Min-max normalize each score list to [0, 1]; a chunk missing from one list
   scores 0 there.
3. Rank by `alpha * vector + (1 - alpha) * bm25` and return the top k.

**Why it fits code documentation:** developer questions mix concepts ("how do I
give a model tools") with exact identifiers (`bind_tools`, `ToolMessage`).
Embeddings capture the first but blur rare identifiers together; BM25 matches
them exactly. Our BM25 tokenizer also splits `snake_case` and `CamelCase`, so
`ChatOllama` matches "ollama".

## 3. How we evaluated

- **46 questions** in `rag_server/eval_questions.json`, each listing the doc
  file(s) that answer it, in three groups:
  - **original (20):** typical questions mixing concepts and API names.
  - **identifier (20):** built around one exact class/function name that
    appears in **exactly one** doc file (e.g. `BlockedContentMiddleware`,
    `max_marginal_relevance_search`), so the right answer is unambiguous.
  - **conceptual (6):** everyday-language paraphrases with no API names
    (e.g. "Make the assistant always reply in a fixed JSON shape").
- **Metrics (k = 5):** **Hit@5**, the share of questions with a correct chunk
  in the top 5; **MRR**, the mean of 1/rank of the first correct chunk
  (1.0 = always ranked first).
- **Compared:** vector-only baseline vs. fusion at alpha = 0.3, 0.5, 0.7.

## 4. Results

### Overall (46 questions)

| Method | Hit@5 | MRR |
|---|---|---|
| Vector only (baseline) | 0.91 | 0.84 |
| Fusion alpha=0.3 | 0.96 | 0.84 |
| **Fusion alpha=0.5 (default)** | **0.96** | **0.85** |
| Fusion alpha=0.7 | 0.93 | 0.82 |

### By question type

| Method | Original (20) Hit / MRR | Identifier (20) Hit / MRR | Conceptual (6) Hit / MRR |
|---|---|---|---|
| Vector only | **1.00 / 0.94** | 0.90 / 0.81 | 0.67 / **0.56** |
| Fusion alpha=0.3 | 0.95 / 0.87 | **1.00 / 0.93** | **0.83** / 0.46 |
| **Fusion alpha=0.5** | 1.00 / 0.90 | **1.00** / 0.92 | 0.67 / 0.47 |
| Fusion alpha=0.7 | 1.00 / 0.90 | 0.95 / 0.83 | 0.67 / 0.50 |

### Where the two methods disagree (rank of first correct chunk, "miss" = not in top 5)

| Question | Type | Vector | Fusion 0.5 |
|---|---|---|---|
| How do I send an image to a model with `ImageContentBlock`? | identifier | miss | 3 |
| `CallCounterMiddleware` example | identifier | miss | 2 |
| `BlockedContentMiddleware` | identifier | 4 | **1** |
| `ClientCredentialsProvider` for MCP OAuth | identifier | 2 | **1** |
| `DynamicToolMiddleware` | identifier | 2 | **1** |
| What is a `ToolMessage` and what is `tool_call_id` used for? | original | 3 | 2 |
| `trim_tokens_to_summarize` | identifier | **1** | 2 |
| How do I define a custom tool with the `@tool` decorator? | original | **1** | 2 |
| Pause the agent for human approval before a tool runs | original | **1** | 2 |
| Make the assistant always reply in a fixed JSON shape | conceptual | **1** | 2 |

### Cost

| | Vector | Fusion 0.5 |
|---|---|---|
| Search latency (avg over 46 queries) | 40 ms | 45 ms |
| Extra memory / startup | none | in-memory BM25 over 995 chunks, built in 0.3 s |

## 5. Insights

1. **Fusion fixes the failure mode it was chosen for.** On exact-identifier
   questions it found the right page every time (Hit@5 0.90 → 1.00) and ranked
   it higher (MRR 0.81 → 0.92). Both vector misses were rare class names
   (`ImageContentBlock`, `CallCounterMiddleware`): their embedding sits close to
   many similar "middleware"/"message" chunks, while BM25 gives the rare token a
   high IDF and pins the one page that contains it.
2. **It slightly hurts pure paraphrases.** When a question shares no words with
   the docs, the BM25 half contributes noise and pushes the best semantic match
   down a place (conceptual MRR 0.56 → 0.47; e.g. "fixed JSON shape" fell from
   rank 1 to 2). Hit@5 was unchanged, so the answer still reaches the agent.
3. **alpha = 0.5 is the best trade-off,** and we kept it as the default. More
   keyword weight (0.3) found one more conceptual question but dropped one
   original question; more vector weight (0.7) lost an identifier hit.
4. **For an agent, Hit@5 matters more than rank 1.** `search_docs` returns five
   chunks into the LLM's context, so moving a correct chunk from rank 1 to 2
   costs little, while a miss means the model writes code from memory. Fusion
   cut misses from 4 to 2 for about 5 ms more per query.
5. **Our first test set hid the benefit.** With only the 20 original questions,
   vector search already scored Hit@5 1.00, and fusion looked slightly *worse*
   (MRR 0.90 vs 0.94). Only questions targeting the technique's purpose (exact
   identifiers) showed its value. Lesson: an evaluation has to include the cases
   the technique is meant to fix.
6. **Two questions fail with every method:** "Check automatically that my
   assistant behaves correctly" (answer: `test/`) and "Answer questions using my
   company's own documents" (answer: `retrieval.mdx`). Neither words nor
   embeddings link "check automatically" to "testing". That is a vocabulary gap,
   which fusion cannot close; query rewriting would address it.

## 6. Agent integration

- In end-to-end runs on Groq (`openai/gpt-oss-120b`), Golu calls `search_docs`
  for LangChain questions and cites the returned source URLs.
- The tool description tells the model that `search_docs` is the primary source
  for LangChain/LangGraph. Without this the model sometimes went straight to the
  external Context7 server, which has a very assertive tool description.
- `search_docs` accepts `k: null` (treated as 5), because the registry now
  allows null for optional parameters and some models send it.

## 7. Limitations and next steps

- **Small test set:** 46 questions, and only 6 conceptual ones, so the
  per-type numbers for that group move a lot with a single question.
- **File-level ground truth:** a hit means "a chunk from the right page", not
  "the exact paragraph".
- **Next steps:**
  - query rewriting / HyDE for vocabulary-gap questions (insight 6)
  - a cross-encoder reranker on the fused top 20
  - more conceptual questions

## 8. Reproduce

```bash
# Once: download docs and build the index (Ollama running, nomic-embed-text pulled)
python -m rag_server.ingest

# Compare baseline vs fusion at three weights and save the numbers
python -m rag_server.evaluate --alphas 0.3 0.5 0.7 --show-misses --out docs/rag-eval-results.json
```
