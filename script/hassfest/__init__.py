"""Manifest validator."""

import ast
from functools import lru_cache
from pathlib import Path


@lru_cache
def ast_parse_module(file_path: Path) -> ast.Module:
    """Parse a module.

    Cached to avoid parsing the same file for each plugin.
    """
    return ast.parse(file_path.read_text())
