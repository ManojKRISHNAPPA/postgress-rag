# PostgreSQL RAG Chat (Streamlit + LangChain + OpenAI)

This app builds a Retrieval-Augmented Generation (RAG) chatbot over PostgreSQL tables hosted on AWS.

## Features

- Connects to PostgreSQL (AWS RDS or any PostgreSQL endpoint).
- Reads all tables in a schema and converts rows to documents.
- Creates embeddings using OpenAI embedding models.
- Stores vectors in a local FAISS index.
- Auto-refreshes embeddings if a new table is added or row counts change.
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

## Notes

- Automatic refresh occurs before each answer.
- If a new table is created in the selected schema, it is detected and re-embedded.
- Current ingestion strategy reads up to the configured row limit per table.
