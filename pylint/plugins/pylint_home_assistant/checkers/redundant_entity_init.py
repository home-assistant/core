"""Checker for entity ``__init__`` methods that only forward to ``super()``.

An ``__init__`` whose entire body is
``super().__init__(<every parameter, unchanged>)`` adds nothing: deleting
it leaves the class with the inherited constructor and identical runtime
behaviour.

Pylint's own ``useless-parent-delegation`` does not cover these, because
it bails out as soon as the override's signature differs from the parent's
-- and narrowing the annotations (``coordinator: FlowItCoordinator``
instead of the base's ``CoordinatorEntity`` type) is exactly what these
constructors do.
"""

from collections import deque

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.module_info import is_integration_module


def _inherited_init(class_node: nodes.ClassDef) -> nodes.FunctionDef | None:
    """Return the ``__init__`` the class would inherit without the override.

    That is the first one along the MRO after the class itself -- which
    is also the one ``super().__init__`` inside the override calls, so
    removing the override cannot change *which* function runs.
    """
    try:
        mro = class_node.mro()
    except astroid.exceptions.AstroidError:
        return None
    for ancestor in mro[1:]:
        for inherited in ancestor.locals.get("__init__", ()):
            return inherited if isinstance(inherited, nodes.FunctionDef) else None
    return None


def _forwarded_call(node: nodes.FunctionDef) -> nodes.Call | None:
    """Return the ``super().__init__(...)`` call that is the whole body.

    ``None`` when the body does anything else. astroid keeps the
    docstring out of ``body`` (in ``doc_node``), so a documented
    constructor still has a single statement here.
    """
    if len(node.body) != 1:
        return None
    match node.body[0]:
        case nodes.Expr(
            value=nodes.Call(
                func=nodes.Attribute(
                    expr=nodes.Call(
                        func=nodes.Name(name="super"), args=[], keywords=[]
                    ),
                    attrname="__init__",
                )
            ) as call
        ):
            return call
    return None


def _is_name(node: nodes.NodeNG, name: str) -> bool:
    """Return True if *node* is a plain reference to the variable *name*."""
    return isinstance(node, nodes.Name) and node.name == name


def _positional_names(args: nodes.Arguments) -> list[str]:
    """Return the positional parameter names, without ``self``.

    The lists are optional on ``Arguments`` nodes that astroid
    synthesizes, hence the ``or ()``.
    """
    return [arg.name for arg in (*(args.posonlyargs or ()), *(args.args or ()))][1:]


def _exposes_same_signature(
    args: nodes.Arguments, inherited: nodes.Arguments, by_keyword: set[str]
) -> bool:
    """Return True if dropping the override keeps every call site valid.

    Removing the override replaces its signature with the inherited one,
    so the two must agree on where a caller's arguments land. Positional
    parameters must line up by index -- a parent that declares the same
    names in another order would silently receive swapped arguments.
    Names matter for the parameters the override itself forwards by
    keyword: the parent must declare each under that exact name, at that
    same index, rather than absorbing it into ``**kwargs``. Keyword-only
    parameters need only to exist in the parent, since they could never
    be passed positionally to begin with. A parent taking *more*
    parameters is fine -- the extra ones have defaults, or the delegating
    call would already fail -- so dropping the override only widens what
    callers may pass.
    """
    own_positional = _positional_names(args)
    inherited_positional = _positional_names(inherited)
    if len(own_positional) > len(inherited_positional):
        return False
    inherited_index = {name: index for index, name in enumerate(inherited_positional)}
    for index, name in enumerate(own_positional):
        if name in by_keyword and inherited_index.get(name) != index:
            return False
    inherited_names = inherited_index.keys() | {
        arg.name for arg in (inherited.kwonlyargs or ())
    }
    return all(arg.name in inherited_names for arg in (args.kwonlyargs or ()))


def _forwarded_by_keyword(args: nodes.Arguments, call: nodes.Call) -> set[str] | None:
    """Return the parameters *call* forwards by keyword, or None.

    ``None`` means *call* is not a plain hand-through: every parameter
    must reach the parent under its own name, either positionally in
    declaration order or as ``name=name``. Anything else -- a
    reordering, a renamed keyword, an expression, an extra or a missing
    argument -- means the constructor is doing work of its own.
    """
    # A default may differ from the parent's, so deleting the override
    # would change behaviour. Out of scope.
    if args.defaults or any(default is not None for default in args.kw_defaults):
        return None

    positional = [arg.name for arg in (*args.posonlyargs, *args.args)]
    if not positional:
        return None
    # ``self`` is bound by ``super()``, never forwarded.
    pending = deque(positional[1:])

    starred_forwarded = False
    for passed in call.args:
        if isinstance(passed, nodes.Starred):
            # ``*args`` may only follow the positionals it comes after.
            if pending or args.vararg is None or starred_forwarded:
                return None
            if not _is_name(passed.value, args.vararg):
                return None
            starred_forwarded = True
            continue
        if starred_forwarded or not pending:
            return None
        if not _is_name(passed, pending.popleft()):
            return None

    if (args.vararg is not None) != starred_forwarded:
        return None

    double_starred_forwarded = False
    by_keyword: list[str] = []
    for keyword in call.keywords:
        if keyword.arg is None:
            if args.kwarg is None or double_starred_forwarded:
                return None
            if not _is_name(keyword.value, args.kwarg):
                return None
            double_starred_forwarded = True
            continue
        if not _is_name(keyword.value, keyword.arg):
            return None
        by_keyword.append(keyword.arg)

    if (args.kwarg is not None) != double_starred_forwarded:
        return None

    expected = [*pending, *(arg.name for arg in args.kwonlyargs)]
    if sorted(by_keyword) != sorted(expected):
        return None
    return set(by_keyword)


class RedundantEntityInitChecker(BaseChecker):
    """Checker for entity constructors that only delegate to ``super()``."""

    name = "home_assistant_redundant_entity_init"
    priority = -1
    msgs = {
        "R7405": (
            "`__init__` of `%s` only forwards its arguments to "
            "`super().__init__`, remove it",
            "home-assistant-redundant-entity-init",
            (
                "Used when an entity class defines an __init__ whose whole "
                "body is super().__init__(...) passing every parameter "
                "through unchanged. The inherited constructor already does "
                "this, so the override can be deleted."
            ),
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Flag an entity ``__init__`` that is pure delegation."""
        if not self._in_integration or node.name != "__init__":
            return
        # A decorator can give the override a purpose of its own.
        if node.decorators is not None:
            return
        parent = node.parent
        if not isinstance(parent, nodes.ClassDef):
            return
        # A class decorator can synthesize its own ``__init__``
        # (``@dataclass`` does), which the override currently suppresses.
        if parent.decorators is not None:
            return
        if not inherits_from_entity(parent):
            return
        if (call := _forwarded_call(node)) is None:
            return
        if (by_keyword := _forwarded_by_keyword(node.args, call)) is None:
            return
        if (inherited := _inherited_init(parent)) is None:
            return
        if not _exposes_same_signature(node.args, inherited.args, by_keyword):
            return
        self.add_message(
            "home-assistant-redundant-entity-init",
            node=node,
            args=(parent.name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantEntityInitChecker(linter))
