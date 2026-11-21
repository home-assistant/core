"""Checker for entity ``__init__`` methods that only forward to ``super()``.

Pylint's ``useless-parent-delegation`` skips these when the override
narrows the annotations, which is the usual reason they exist.
"""

from collections import deque

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.module_info import is_integration_module


def _inherited_init(class_node: nodes.ClassDef) -> nodes.FunctionDef | None:
    """Return the ``__init__`` that ``super().__init__`` calls."""
    try:
        mro = class_node.mro()
    except astroid.exceptions.AstroidError:
        return None
    for ancestor in mro[1:]:
        for inherited in ancestor.locals.get("__init__", ()):
            return inherited if isinstance(inherited, nodes.FunctionDef) else None
    return None


def _rerouted_by_descendant(
    class_node: nodes.ClassDef, inherited: nodes.FunctionDef
) -> bool:
    """Return True if a subclass makes ``super()`` reach another ``__init__``.

    Subclasses in other modules are not checked.
    """
    for other in class_node.root().nodes_of_class(nodes.ClassDef):
        if other is class_node:
            continue
        try:
            mro = other.mro()
        except astroid.exceptions.AstroidError:
            continue
        if class_node not in mro:
            continue
        for ancestor in mro[mro.index(class_node) + 1 :]:
            if "__init__" in ancestor.locals:
                if ancestor.locals["__init__"][0] is not inherited:
                    return True
                break
    return False


def _forwarded_call(node: nodes.FunctionDef) -> nodes.Call | None:
    """Return the ``super().__init__(...)`` call if it is the whole body.

    astroid keeps the docstring out of ``body``.
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

    astroid can leave these lists as None on synthesized nodes.
    """
    return [arg.name for arg in (*(args.posonlyargs or ()), *(args.args or ()))][1:]


def _keyword_start(args: nodes.Arguments) -> int:
    """Return the first ``_positional_names`` index callers may pass by keyword."""
    return max(len(args.posonlyargs or ()) - 1, 0)


def _exposes_same_signature(
    args: nodes.Arguments, inherited: nodes.Arguments, by_keyword: set[str]
) -> bool:
    """Return True if dropping the override keeps every call site valid.

    Each parameter that is passed by keyword must have the same name and
    index in the parent, and the parent must accept it by keyword, not
    absorb it into ``**kwargs``. Extra parent parameters are fine.
    """
    own_positional = _positional_names(args)
    inherited_positional = _positional_names(inherited)
    if len(own_positional) > len(inherited_positional):
        return False
    own_keyword_start = _keyword_start(args)
    inherited_keyword_start = _keyword_start(inherited)
    inherited_index = {name: index for index, name in enumerate(inherited_positional)}
    for index, name in enumerate(own_positional):
        keyword_capable = index >= own_keyword_start
        if not keyword_capable and name not in by_keyword:
            continue
        if inherited_index.get(name) != index:
            return False
        if index < inherited_keyword_start:
            return False
    inherited_names = inherited_index.keys() | {
        arg.name for arg in (inherited.kwonlyargs or ())
    }
    return all(arg.name in inherited_names for arg in (args.kwonlyargs or ()))


def _forwarded_by_keyword(args: nodes.Arguments, call: nodes.Call) -> set[str] | None:
    """Return the parameters *call* forwards by keyword.

    Return None unless every parameter is forwarded unchanged, either
    positionally in order or as ``name=name``.
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
        "R7407": (
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
        # With ``@overload`` stubs next to it, removing the implementation
        # leaves a stub as the runtime constructor.
        if len(parent.locals["__init__"]) > 1:
            return
        if not inherits_from_entity(parent):
            return
        if (call := _forwarded_call(node)) is None:
            return
        if (by_keyword := _forwarded_by_keyword(node.args, call)) is None:
            return
        if (inherited := _inherited_init(parent)) is None:
            return
        # A decorator (``@abstractmethod``, a wrapper) can make the override
        # necessary or change how the inherited constructor is called.
        if inherited.decorators is not None:
            return
        if not _exposes_same_signature(node.args, inherited.args, by_keyword):
            return
        if _rerouted_by_descendant(parent, inherited):
            return
        self.add_message(
            "home-assistant-redundant-entity-init",
            node=node,
            args=(parent.name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantEntityInitChecker(linter))
