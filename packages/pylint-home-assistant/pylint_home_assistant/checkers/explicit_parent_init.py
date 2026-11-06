"""Checker for entity constructors calling ``Base.__init__(self, ...)``.

When the named base owns the first ``__init__`` along the MRO after the
class itself, ``super().__init__(...)`` resolves to that same function,
so the explicit form only hides that and keeps the redundant-constructor
check from seeing through it.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.module_info import is_integration_module


def _is_super_init_call(call: nodes.Call) -> bool:
    """Return True if *call* is ``super(...).__init__(...)``."""
    match call.func:
        case nodes.Attribute(
            attrname="__init__",
            expr=nodes.Call(func=nodes.Name(name="super")),
        ):
            return True
    return False


def _is_explicit_init_call(call: nodes.Call, self_name: str) -> bool:
    """Return True if *call* is ``<Base>.__init__(self, ...)``."""
    match call:
        case nodes.Call(
            func=nodes.Attribute(
                attrname="__init__", expr=nodes.Name() | nodes.Attribute()
            ),
            args=[nodes.Name(name=name), *_],
        ) if name == self_name:
            return True
    return False


def _mro_next_init_owner(class_node: nodes.ClassDef) -> nodes.ClassDef | None:
    """Return the class owning the ``__init__`` that ``super()`` resolves to.

    ``None`` when the MRO cannot be trusted: astroid leaves out bases it
    cannot infer, such as a subscripted ``Generic`` class, and would then
    point at a later base than Python does.
    """
    try:
        mro = class_node.mro()
    except astroid.exceptions.AstroidError:
        return None
    mro_qnames = {ancestor.qname() for ancestor in mro}
    if any(
        ancestor.qname() not in mro_qnames
        for ancestor in extended_ancestors(class_node)
    ):
        return None
    for ancestor in mro[1:]:
        if "__init__" in ancestor.locals:
            return ancestor
    return None


class ExplicitParentInitChecker(BaseChecker):
    """Checker for explicit parent constructor calls ``super()`` can replace."""

    name = "home_assistant_explicit_parent_init"
    priority = -1
    msgs = {
        "R7407": (
            "Use `super().__init__(...)` instead of `%s.__init__(self, ...)`",
            "home-assistant-explicit-parent-init",
            (
                "Used when an entity __init__ calls a base class constructor "
                "by name while super().__init__ resolves to the same "
                "constructor and no other base constructor is called."
            ),
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Flag a lone explicit parent constructor call ``super()`` can replace."""
        if not self._in_integration or node.name != "__init__":
            return
        parent = node.parent
        if not isinstance(parent, nodes.ClassDef) or not node.args.args:
            return
        if not inherits_from_entity(parent):
            return

        self_name = node.args.args[0].name
        init_calls = [
            call
            for call in node.nodes_of_class(
                nodes.Call,
                skip_klass=(nodes.FunctionDef, nodes.Lambda, nodes.ClassDef),
            )
            if _is_super_init_call(call) or _is_explicit_init_call(call, self_name)
        ]
        # Several base constructors (e.g. an integration base plus
        # ``ImageEntity``) have to be called by name, since one ``super()``
        # chain cannot pass each its own arguments.
        if len(init_calls) != 1 or _is_super_init_call(call := init_calls[0]):
            return

        try:
            target = next(call.func.expr.infer())
        except astroid.exceptions.InferenceError, StopIteration:
            return
        if not isinstance(target, nodes.ClassDef):
            return
        if (owner := _mro_next_init_owner(parent)) is None:
            return
        if owner.qname() != target.qname():
            return
        self.add_message(
            "home-assistant-explicit-parent-init",
            node=call,
            args=(call.func.expr.as_string(),),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ExplicitParentInitChecker(linter))
