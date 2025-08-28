# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""pyinvoke task definitions used for linting/fixing code."""

from invoke import Context, task


@task(
    help={
        "fix": "Apply fixes instead of just linting",
        "files": "Files or directories to check/fix",
    }
)
def black(ctx: Context, fix: bool = False, files: str = ".") -> None:
    """
    Run Black for code formatting.

    Extra options are defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        fix: Whether to apply fixes. Defaults to False.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    if fix:
        cmd = f"black {files}"
    else:
        cmd = f"black --check --diff {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "fix": "Apply fixes instead of just linting",
        "files": "Files or directories to check/fix",
    }
)
def isort(ctx: Context, fix: bool = False, files: str = ".") -> None:
    """
    Run isort for import sorting.

    Extra options are defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        fix: Whether to apply fixes. Defaults to False.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    if fix:
        cmd = f"isort --profile black {files}"
    else:
        cmd = f"isort --profile black --check-only --diff {files}"

    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "fix": "Apply fixes instead of just linting",
        "files": "Files or directories to check/fix",
    }
)
def ruff(ctx: Context, fix: bool = False, files: str = ".") -> None:
    """
    Run Ruff for linting and fixing issues.

    Extra options are defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        fix: Whether to apply fixes. Defaults to False.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    if fix:
        cmd = f"ruff check --fix {files}"
    else:
        cmd = f"ruff check {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "files": "Files or directories to check/fix",
    }
)
def pydocstyle(ctx: Context, files: str = ".") -> None:
    """
    Run pydocstyle for docstring linting.

    Extra options are defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    cmd = f"pydocstyle --config=pyproject.toml {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "files": "Files or directories to check/fix",
    }
)
def pydoclint(ctx: Context, files: str = ".") -> None:
    """
    Run pydoclint for docstring linting.

    Extra options are defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    cmd = f"pydoclint {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    pre=[black, isort, ruff, pydocstyle, pydoclint],
    help={
        "files": "Files or directories to lint",
    },
)
def lint(ctx: Context, files: str = ".") -> None:
    """
    Run all linters.

    Each linter has extra options defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    print("Linting completed.")


@task(
    help={
        "files": "Files or directories to lint",
    },
)
def fixers(ctx: Context, files: str = ".") -> None:
    """
    Run all fixers.

    Each linter has extra options defined in pyproject.toml.

    Args:
        ctx: The pyinvoke subprocess context.
        files: File matching pattern. Defaults to ".".

    Returns:
        None: No return value.
    """
    black(ctx, fix=True, files=files)
    isort(ctx, fix=True, files=files)
    # NOTE: we are not ready to use ruff to autofix code
    # ruff(ctx, fix=True, files=files)
    print("-> Fixers completed.")


@task(
    help={
        "files": "Space-separated list of files to include",
        "expr": "Run tests which match substring expression ('-k' pytest arg)",
    },
)
def pytest(
    ctx: Context,
    files: str = "tests",
    expr: str = "",
) -> None:
    """
    Run pytest unit/integration tests.

    Args:
        ctx: The pyinvoke subprocess context.
        files: Space-separated list of files to include.
        expr: Run tests which match substring expression ('-k' pytest arg).

    Returns:
        None: No return value.
    """
    if expr:
        cmd = f"pytest {files} -k {expr}"
    else:
        cmd = f"pytest {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "files": "Space-separated list of files to include",
        "expr": "Run tests which match substring expression ('-k' pytest arg)",
    },
)
def coverage(
    ctx: Context,
    files: str = "tests",
    expr: str = "",
) -> None:
    """
    Run pytest unit/integration tests.

    Args:
        ctx: The pyinvoke subprocess context.
        files: Space-separated list of files to include.
        expr: Run tests which match substring expression ('-k' pytest arg).

    Returns:
        None: No return value.
    """
    cmd = f"pytest --cov=app --cov-report term-missing {files}"
    if expr:
        cmd += f" -k {expr}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)


@task(
    help={
        "files": "Space-separated list of files to include",
        "exclude": "Regex of files/directories to ignore",
    },
)
def mypy(
    ctx: Context,
    files: str = "src/app tasks.py",
    exclude: str = "^alembic/",
) -> None:
    """
    Check for PEP 484 compliance using mypy.

    Args:
        ctx: The pyinvoke subprocess context.
        files: Space-separated list of files to include.
        exclude: Ignore file/directories matching this regex.

    Returns:
        None: No return value.
    """
    cmd = f"mypy --exclude={exclude} {files}"
    print(f"-> Running: {cmd}")
    ctx.run(cmd, pty=False, warn=False)
