"""Safe writable-copy helpers for the local ProcureFlow demo."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import duckdb


EXPECTED_TABLES = {
    "app_users",
    "procurement_requests",
    "request_history",
    "request_references",
}


class DemoWorkspaceError(ValueError):
    """Raised when a local demo workspace cannot be created or reset."""


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _validate_baseline(path: Path) -> None:
    if not path.is_file():
        raise DemoWorkspaceError(f"Demo baseline was not found: {path}")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                  AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
    finally:
        connection.close()
    if tables != EXPECTED_TABLES:
        raise DemoWorkspaceError(
            "The demo baseline must contain exactly the four approved tables."
        )


def create_demo_workspace(
    baseline_path: str | Path,
    *,
    workspace_directory: str | Path,
    workspace_name: str | None = None,
) -> Path:
    """Create a uniquely named writable copy of the approved baseline."""

    baseline = _resolved(baseline_path)
    _validate_baseline(baseline)
    directory = _resolved(workspace_directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = workspace_name or f"procureflow_session_{uuid4().hex[:10]}.duckdb"
    destination = (directory / name).resolve()
    if destination == baseline:
        raise DemoWorkspaceError("A demo workspace cannot replace the baseline.")
    if destination.exists():
        raise DemoWorkspaceError(f"Demo workspace already exists: {destination}")
    shutil.copy2(baseline, destination)
    return destination


def reset_demo_workspace(
    workspace_path: str | Path,
    *,
    baseline_path: str | Path,
) -> Path:
    """Reset one explicit session copy from the approved baseline."""

    workspace = _resolved(workspace_path)
    baseline = _resolved(baseline_path)
    _validate_baseline(baseline)
    if workspace == baseline:
        raise DemoWorkspaceError("The approved baseline cannot be reset in place.")
    if not workspace.is_file():
        raise DemoWorkspaceError(f"Demo workspace was not found: {workspace}")
    shutil.copy2(baseline, workspace)
    return workspace


def is_baseline_path(path: str | Path, baseline_path: str | Path) -> bool:
    """Return whether a path resolves to the protected baseline."""

    return _resolved(path) == _resolved(baseline_path)
