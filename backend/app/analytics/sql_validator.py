import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_RESULT_ROWS = 500

FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Copy,
    exp.Grant,
    exp.Revoke,
)

FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_exec",
}


class SQLValidationError(ValueError):
    """Raised when an LLM-generated SQL query violates security or safety rules."""


def validate_and_prepare_sql(raw_sql: str, allowed_table: str) -> str:
    """
    Parse a PostgreSQL query into an AST, enforce strict read-only & single-table
    rules, apply a row LIMIT if missing, and return clean PostgreSQL SQL.
    """
    cleaned = raw_sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SQLValidationError("SQL query is empty.")

    try:
        statements = sqlglot.parse(cleaned, read="postgres")
    except ParseError as exc:
        raise SQLValidationError(f"Invalid SQL syntax: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError("Only a single SQL statement is permitted.")

    tree = statements[0]

    # 1. Root statement must be a SELECT or set operation (UNION/INTERSECT/EXCEPT)
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLValidationError(
            f"Only SELECT queries are permitted (got {type(tree).__name__})."
        )

    # 2. Block any forbidden DDL/DML nodes anywhere in the AST (including inside CTEs)
    for node_type in FORBIDDEN_NODES:
        if tree.find(node_type) is not None:
            raise SQLValidationError(
                f"Forbidden SQL operation detected: {node_type.__name__}."
            )

    # 3. Block dangerous PostgreSQL functions
    for func in tree.find_all(exp.Anonymous, exp.Func):
        func_name = (func.name or "").lower()
        if func_name in FORBIDDEN_FUNCTIONS:
            raise SQLValidationError(f"Forbidden SQL function: '{func_name}'.")

    # 4. Verify every referenced table is either a local CTE or the single allowed dataset table
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    target_table = allowed_table.lower()

    for table in tree.find_all(exp.Table):
        if table.db or table.catalog:
            raise SQLValidationError(
                "Cross-schema or system catalog queries are not permitted."
            )
        table_name = table.name.lower()
        if table_name not in cte_names and table_name != target_table:
            raise SQLValidationError(
                f"Access to table '{table.name}' is not permitted. "
                f"Only '{allowed_table}' may be queried."
            )

    # 5. Enforce a LIMIT cap if none was provided
    if isinstance(tree, exp.Select) and tree.args.get("limit") is None:
        tree = tree.limit(MAX_RESULT_ROWS)

    return tree.sql(dialect="postgres")