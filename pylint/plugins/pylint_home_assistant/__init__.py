"""Home Assistant Pylint plugin package.

Registers all Home Assistant-specific checkers with pylint.
Checker modules are auto-discovered from the ``checkers`` subpackage —
any module that defines a ``register(linter)`` function will be loaded.
"""

import importlib
import pkgutil

from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant import checkers


def register(linter: PyLinter) -> None:
    """Register all Home Assistant checkers which have not been registered yet."""
    existing_checker_types: set[type] = {
        type(checker)
        for checkers_list in linter._checkers.values()  # noqa: SLF001
        for checker in checkers_list
    }
    # Auto-discover and register all checker modules under ``checkers/``.
    for module_info in pkgutil.walk_packages(
        checkers.__path__, prefix=f"{checkers.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        if not hasattr(module, "register"):
            continue
        # Skip modules whose checker class is already registered (worker
        # re-registration in parallel mode). Only consider checker classes
        # defined in the module itself, not ones imported from pylint.
        module_checker_types = {
            value
            for value in vars(module).values()
            if (
                isinstance(value, type)
                and issubclass(value, BaseChecker)
                and value.__module__ == module.__name__
            )
        }
        if module_checker_types and module_checker_types <= existing_checker_types:
            continue
        module.register(linter)
