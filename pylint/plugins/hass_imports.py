"""Plugin for checking imports."""
from __future__ import annotations

from dataclasses import dataclass
import re

from astroid import Import, ImportFrom, Module
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


@dataclass
class ObsoleteImportMatch:
    """Class for pattern matching."""

    constant: re.Pattern
    reason: str


_OBSOLETE_IMPORT: dict[str, list[ObsoleteImportMatch]] = {
    "homeassistant.components.sensor": [
        ObsoleteImportMatch(
            reason="replaced by SensorStateClass enum",
            constant=re.compile(r"^STATE_CLASS_(\w*)$"),
        ),
    ],
    "homeassistant.components.light": [
        ObsoleteImportMatch(
            reason="replaced by LightEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(EFFECT|FLASH|TRANSITION)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by color modes",
            constant=re.compile(r"^SUPPORT_(BRIGHTNESS|COLOR_TEMP|COLOR|WHITE_VALUE)$"),
        ),
    ],
}


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
        "W0012": (
            "%s is deprecated, %s",
            "hass-deprecated-import",
            "Used when import is deprecated",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self.current_package: str | None = None

    def visit_module(self, node: Module) -> None:
        """Called when a Module node is visited."""
        if node.package:
            self.current_package = node.name
        else:
            # Strip name of the current module
            self.current_package = node.name[: node.name.rfind(".")]

    def visit_import(self, node: Import) -> None:
        """Called when a Import node is visited."""
        for module, _alias in node.names:
            if module.startswith(f"{self.current_package}."):
                self.add_message("hass-relative-import", node=node)

    def visit_importfrom(self, node: ImportFrom) -> None:
        """Called when a ImportFrom node is visited."""
        if node.level is not None:
            return
        if node.modname == self.current_package or node.modname.startswith(
            f"{self.current_package}."
        ):
            self.add_message("hass-relative-import", node=node)
        elif obsolete_imports := _OBSOLETE_IMPORT.get(node.modname):
            for name_tuple in node.names:
                for obsolete_import in obsolete_imports:
                    if import_match := obsolete_import.constant.match(name_tuple[0]):
                        self.add_message(
                            "hass-deprecated-import",
                            node=node,
                            args=(import_match.string, obsolete_import.reason),
                        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassImportsFormatChecker(linter))
