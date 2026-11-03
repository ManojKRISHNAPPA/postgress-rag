# PostgreSQL RAG Chat (Streamlit + LangChain + OpenAI)

This app builds a Retrieval-Augmented Generation (RAG) chatbot over PostgreSQL tables hosted on AWS.

## Features

- Connects to PostgreSQL (AWS RDS or any PostgreSQL endpoint).
- Reads all tables in a schema and converts rows to documents.
- Uses Recursive Character Text Splitting for better retrieval on long rows.
- Creates embeddings using OpenAI embedding models.
- Stores vectors in a local FAISS index.
- Auto-refreshes embeddings if a new table is added or row counts change.
- Hybrid answer mode:
- SQL mode for list/count/top/filter/reporting questions.
- RAG mode for semantic/business explanation questions.
- Strict fallback behavior: returns "I don't know based on the indexed data." when retrieval confidence is low.
- Chat UI built with Streamlit.
- OpenAI key is entered directly in the UI (not loaded from `.env`).

## 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Optional env defaults

You can copy `.env.example` to `.env` to prefill DB fields in the sidebar.

```bash
cp .env.example .env
```

## 3) Run app

```bash
streamlit run app.py
```

## 4) Use

1. Fill DB connection fields in sidebar.
2. Paste OpenAI API key in sidebar input.
3. Click **Connect / Refresh Index**.
4. Ask questions in chat.

## Teaching the Two-File Application

Start with [rag_core.py](rag_core.py), then [app.py](app.py). Both include comments
explaining why each stage exists and where the classroom demo needs production work.

1. Build the PostgreSQL URI and inspect the schema.
2. Convert sampled table rows into LangChain Documents with source metadata.
3. Split long records using recursive character splitting and overlap.
4. Embed chunks and store/search their vectors with FAISS.
5. Route exact lists/aggregates to SQL and semantic explanations to RAG.
6. Supply retrieved excerpts to the model and display those exact excerpts.
7. Use Streamlit session state to redraw the UI and conversation.

The sidebar's **Answer mode** can change without rebuilding the index:

| Mode | Example | Behavior |
| --- | --- | --- |
| `auto` | "Explain customer churn reasons" | Uses semantic retrieval rather than routing merely on "customer" |
| `rag` | "What does onboarding involve?" | Answers from retrieved passages and requests source labels such as `[S1]` |
| `sql` | "How many customers are there?" | Generates a query over the schema; reports failure rather than silently answering from sampled text |

Auto mode uses a heuristic, not a universal intent classifier. If SQL fails in auto
mode, a visible warning identifies the semantic fallback as indexed excerpts rather
than a complete query result. Source labels show provenance, not proof of correctness.

You can ask any question, but the chatbot must not invent answers absent from the
selected database/index. It returns "I don't know based on the indexed data." when
evidence is unavailable. Displayed conversation history is not model memory, so use
self-contained questions. Retrieval only covers the configured sample of each table.

Important remaining limits: same-count updates are not detected, the cache is shared,
saved FAISS metadata uses trusted-only pickle loading, and regex SQL checks are not a
security sandbox. Use a restricted read-only database role; evaluate real questions
and strengthen these controls before production use.

## 5) Production-style querying behavior

This app now routes queries by intent:

- Structured queries (for example: "list top 200 customers by revenue") are translated into safe read-only SQL, executed, and returned as table output.
- Semantic queries (for example: "explain churn drivers") use RAG over chunked context.

Safety controls:

- Read-only SQL only (SELECT/CTE).
- Single statement only.
- Result size capped through enforced LIMIT.

## 6) Run tests

```bash
pytest -q
```

## Notes

- Automatic refresh occurs before each answer.
- If a new table is created in the selected schema, it is detected and re-embedded.
- Ingestion reads up to the configured row limit per table, then chunk-splits those records for better retrieval quality.




```
Depends mainly on the NVD data feed download (first run) rather than the tool itself:

First run (no NVD API key): Can take 20–60+ minutes, sometimes longer, because NVD enforces strict public rate limits on the CVE feed API.
First run (with NVD API key): Usually 5–15 minutes — an API key raises the rate limit significantly. Get a free key at nvd.nist.gov/developers/request-an-api-key.
Subsequent runs: Much faster (1–5 minutes), since it only pulls incremental updates if the local NVD cache is persisted between builds.
The scan itself (after data is downloaded) is usually quick — a few seconds to a couple minutes depending on project size.
Recommendation for your Jenkins setup: persist the dependency-check data directory (usually ~/.m2/repository/org/owasp or wherever odcInstallation caches it, typically <tool-home>/data) across builds using a Jenkins agent with a persistent workspace/volume, and configure an NVD API key via --nvdApiKey in additionalArguments, otherwise every build could stall for a long time or hit rate-limit failures.

Want me to update the Jenkinsfile dependencyCheck step to add an NVD API key credential and cache the data directory?

```
