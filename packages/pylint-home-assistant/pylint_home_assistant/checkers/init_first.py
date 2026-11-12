"""Checker that the constructor is the first method of a class.

``C7417`` (``home-assistant-init-not-first``)
---------------------------------------------
Fires when an instance method or property is defined before ``__init__``.
Class attributes may precede ``__init__``, as may static methods and class
methods (including implicit ones such as ``__new__`` and
``__init_subclass__``), since those are commonly alternative constructors
or factories such as ``async_get_options_flow``.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module


class HassInitFirstChecker(BaseChecker):
    """Checker that ``__init__`` is defined before other instance methods."""

    name = "home_assistant_init_first"
    priority = -1
    msgs = {
        "C7417": (
            "`__init__` of class `%s` should be defined before `%s`",
            "home-assistant-init-not-first",
            (
                "Used when an instance method or property is defined before "
                "`__init__`. Define the constructor right after the class "
                "attributes so the class reads top-down."
            ),
        ),
    }
    options = ()

    _check_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Cache whether the module is an integration module."""
        self._check_module = is_integration_module(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag ``__init__`` defined after an instance method or property."""
        if not self._check_module:
            return
        first_method: nodes.FunctionDef | None = None
        for item in node.body:
            if not isinstance(item, nodes.FunctionDef):
                continue
            if item.name == "__init__":
                if first_method is not None:
                    self.add_message(
                        "home-assistant-init-not-first",
                        node=item,
                        args=(node.name, first_method.name),
                    )
                return
            if first_method is None and item.type == "method":
                first_method = item


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassInitFirstChecker(linter))
