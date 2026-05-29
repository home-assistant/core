"""Home Assistant Pylint plugin package.

Registers all Home Assistant-specific checkers with pylint.
Checker modules are auto-discovered from the ``checkers`` subpackage —
any module that defines a ``register(linter)`` function will be loaded.
"""

import importlib
import pkgutil

from pylint.lint import PyLinter

from pylint_home_assistant import checkers


def register(linter: PyLinter) -> None:
    """Register all Home Assistant checkers."""
    # Auto-discover and register all checker modules under ``checkers/``.
    for module_info in pkgutil.walk_packages(
        checkers.__path__, prefix=f"{checkers.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        if hasattr(module, "register"):
            module.register(linter)
