# Architecture Decision Guide: PostgreSQL MCP vs RAG

This guide explains when to use direct PostgreSQL querying (MCP) and when to use Retrieval-Augmented Generation (RAG), plus why a hybrid approach is usually best in production.

## 1) Problem Statement

You have two capabilities:

- PostgreSQL MCP: query live relational data directly with SQL.
- RAG over PostgreSQL: embed row/doc context and answer through semantic retrieval + LLM.

Each is strong for different workloads.

## 2) Quick Decision Matrix

| Question type | Best mode | Why |
|---|---|---|
| "List top 500 customers by revenue" | SQL (MCP) | Exact, deterministic, auditable |
| "How many active customers this month?" | SQL (MCP) | Precise aggregation over live data |
| "Why did churn increase in enterprise segment?" | RAG | Semantic reasoning over context |
| "Explain onboarding policy in simple terms" | RAG | Natural language synthesis |
| "Show customer + latest invoice + payment status" | SQL (MCP) | Multi-table joins are exact in SQL |
| "What are recurring support themes from notes?" | RAG | Fuzzy topic retrieval |

## 3) PostgreSQL MCP

### Advantages

- Real-time and exact answers from source of truth.
- Best for structured analytics: filters, joins, counts, sums, top-N.
- No embedding/index lifecycle management.
- High auditability through explicit SQL.

### Disadvantages

- LLM-generated SQL can be wrong or expensive without guardrails.
- Requires strict read-only and resource constraints for safety.
- Not ideal for fuzzy semantic questions.

## 4) RAG

### Advantages

- Better for semantic, explanatory, and context-heavy questions.
- Handles natural language ambiguity better than strict SQL.
- Can combine multiple context sources in one answer.

### Disadvantages

- Retrieval can miss relevant chunks (approximate, not perfect).
- Index can become stale if refresh strategy is weak.
- Embedding and vector storage add cost and operations overhead.

## 5) Why Hybrid Is Needed

A single mode causes predictable failures:

- SQL-only systems struggle with semantic/explanatory asks.
- RAG-only systems struggle with exact metrics and long lists.

Hybrid routing gives:

- Precision for numeric/reporting questions (SQL path).
- Flexibility for semantic questions (RAG path).
- Better reliability with fallback behavior.

## 6) Recommended Production Routing Policy

1. Detect intent:
   - Structured intent keywords: list, top, count, group by, revenue, total, average.
   - Route structured intent to SQL path first.
2. Enforce SQL safety:
   - Allow only SELECT/CTE.
   - Block mutation DDL/DML statements.
   - Single statement only.
   - Enforce LIMIT cap.
3. If SQL fails safety or execution:
   - Fallback to RAG path.
4. For semantic intent:
   - Use RAG with confidence threshold.
   - If below threshold, answer: "I don't know based on the indexed data."

## 7) Operational Controls

- Set query timeout and max rows for SQL path.
- Add table/column allowlist for sensitive schemas.
- Log routed mode, generated SQL, latency, and fallback rate.
- Rebuild embeddings on schema/table-row-count change.
- Track answer quality metrics separately for SQL and RAG modes.

## 8) Practical Query Examples

### SQL path examples

- "List top 200 customers by annual revenue."
- "Count customers by region for Q2."
- "Show overdue invoices older than 45 days."
- "Top 20 products by margin in last 30 days."

### RAG path examples

- "Summarize reasons for churn from notes."
- "Explain onboarding flow for SMB customers."
- "What issues are repeatedly reported by premium users?"

## 9) Decision Summary

Use SQL MCP whenever correctness and exactness are mandatory.
Use RAG whenever semantic understanding and narrative synthesis are required.
Use hybrid routing in production for balanced accuracy, safety, and usability.
