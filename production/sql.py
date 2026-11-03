"""Lesson 5: parse SQL structurally; let PostgreSQL enforce permissions too."""

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope
from sqlalchemy import MetaData, Table, text
from sqlalchemy.engine import Engine

from production.config import Settings
from production.database import read_transaction


# Conservative on purpose: a SELECT can invoke a dangerous function. Expand
# this only with tests and a security review, never with arbitrary pg_* calls.
ALLOWED_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "LOWER",
                     "UPPER", "LENGTH", "ROUND", "ABS", "CAST", "EXTRACT",
                     "DATE_TRUNC", "TIMESTAMP_TRUNC", "NULLIF"}


def schema_catalog(engine: Engine, settings: Settings) -> dict:
    catalog = {settings.schema: {}}
    with read_transaction(engine, settings.statement_timeout_ms) as conn:
        for spec in settings.tables:
            table = Table(spec.name, MetaData(), schema=settings.schema, autoload_with=conn)
            catalog[settings.schema][spec.name] = {
                name: str(table.c[name].type) for name in spec.columns
            }
    return catalog


def guard_sql(sql: str, catalog: dict, limit: int) -> str:
    """Allow one SELECT/CTE over the catalog; cap the OUTERMOST result only."""
    if limit <= 0 or len(sql) > 20_000:
        raise ValueError("Invalid SQL budget.")
    try:
        statements = sqlglot.parse(sql, read="postgres")
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise ValueError("Only one SELECT or SELECT-based CTE is supported.")
        tree = statements[0]
        for node in tree.walk():
            if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create,
                                 exp.Drop, exp.Alter, exp.Into, exp.Lock, exp.Command)):
                raise ValueError("Mutation, SELECT INTO, and row locks are forbidden.")
            if isinstance(node, exp.Func):
                if isinstance(node.parent, exp.Dot):
                    raise ValueError("Schema-qualified function calls are not permitted.")
                name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name()
                if name not in ALLOWED_FUNCTIONS:
                    raise ValueError(f"Function not approved: {name}")
            if isinstance(node, exp.DataType) and node.this == exp.DataType.Type.USERDEFINED:
                raise ValueError("User-defined casts are not permitted.")

        # A CTE alias is not a physical database table. Scope resolution makes
        # that distinction, unlike matching table names with regexes.
        for scope in traverse_scope(tree):
            for source in scope.sources.values():
                if isinstance(source, exp.Table):
                    if source.catalog or source.db not in catalog or source.name not in catalog[source.db]:
                        raise ValueError("Queries must use explicitly allowed schema-qualified tables.")
        tree = qualify(tree, dialect="postgres", schema=catalog)
        outer_limit = tree.args.get("limit")
        if outer_limit is not None:
            expression = outer_limit.expression
            if not isinstance(expression, exp.Literal) or not expression.is_int:
                raise ValueError("LIMIT must be a nonnegative integer literal.")
            limit = min(limit, int(expression.this))
        return tree.limit(limit).sql(dialect="postgres")
    except sqlglot.errors.SqlglotError as exc:
        raise ValueError("SQL parsing or column validation failed.") from exc


def execute_guarded(engine: Engine, sql: str, settings: Settings) -> dict:
    # Guard again at the execution boundary, even if a caller already did so.
    safe_sql = guard_sql(sql, schema_catalog(engine, settings), settings.sql_limit)
    with read_transaction(engine, settings.statement_timeout_ms) as conn:
        result = conn.execute(text(safe_sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(settings.sql_limit)]
    return {"mode": "sql", "sql": safe_sql, "columns": columns, "rows": rows,
            "capped": len(rows) == settings.sql_limit, "sources": []}