"""Plugin for checking imports."""
from __future__ import annotations

from astroid import Import, ImportFrom, Module
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


class HassImportsFormatChecker(BaseChecker):  # type: ignore[misc]
    """Checker for imports."""

    __implements__ = IAstroidChecker

    name = "hass_imports"
    priority = -1
    msgs = {
        "W0011": (
            "Relative import should be used",
            "hass-relative-import",
            "Used when absolute import should be replaced with relative import",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self.current_module: str | None = None

    def visit_module(self, node: Module) -> None:
        """Called when a Import node is visited."""
        self.current_module = node.name

    def visit_import(self, node: Import) -> None:
        """Called when a Import node is visited."""
        for module, _alias in node.names:
            if module.startswith(f"{self.current_module}."):
                self.add_message("hass-relative-import", node=node)

    def visit_importfrom(self, node: ImportFrom) -> None:
        """Called when a ImportFrom node is visited."""
        if node.level is not None:
            return
        if node.modname == self.current_module or node.modname.startswith(
            f"{self.current_module}."
        ):
            self.add_message("hass-relative-import", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassImportsFormatChecker(linter))
