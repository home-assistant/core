"""Checker for menu_options in config flow async_show_menu calls.

Every option passed to ``self.async_show_menu(menu_options=...)`` becomes a
``next_step_id`` the user can select, which the flow manager dispatches to an
``async_step_<option>`` method. If no such method exists the flow raises
``UnknownStep`` at runtime when the user picks that option.

This checker validates the statically resolvable forms of ``menu_options``
(a literal list/tuple/set of strings, or a literal dict whose keys are the
step ids) against the ``async_step_*`` methods defined on the enclosing flow
class and its ancestors. Dynamic forms (comprehensions, unresolved variables)
are skipped to avoid false positives.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import parse_module

_STEP_PREFIX = "async_step_"


def _safe_infer(node: nodes.NodeNG) -> nodes.NodeNG | None:
    """Infer a single unambiguous value for *node*, else None.

    A name assigned in several branches infers to more than one value; we
    reject that (rather than trusting the first) so the checker only acts on
    an unambiguous inference. ``pylint``'s ``safe_infer`` only rejects results
    of *differing type*, so it would accept two different string lists here --
    hence the explicit single-result check.
    """
    try:
        inferred = list(node.infer())
    except astroid.InferenceError:
        return None
    if len(inferred) != 1 or inferred[0] is astroid.Uninferable:
        return None
    return inferred[0]


def _const_str_elements(elements: list[nodes.NodeNG]) -> set[str] | None:
    """Return the string values of *elements*, or None if any is not a string."""
    step_ids: set[str] = set()
    for element in elements:
        if not isinstance(element, nodes.Const) or not isinstance(element.value, str):
            return None
        step_ids.add(element.value)
    return step_ids


def _resolve_step_ids(node: nodes.NodeNG) -> set[str] | None:
    """Resolve the step ids referenced by a ``menu_options`` value.

    Returns the set of step ids for the statically resolvable forms (a literal
    sequence of strings or a literal dict keyed by strings), or None when the
    value cannot be resolved (and should therefore be skipped).
    """
    if isinstance(node, (nodes.List, nodes.Tuple, nodes.Set)):
        return _const_str_elements(node.elts)
    if isinstance(node, nodes.Dict):
        return _const_str_elements([key for key, _ in node.items])

    # Variables/constants: only trust an inferred literal collection.
    inferred = _safe_infer(node)
    if inferred is None or inferred is node:
        return None
    if isinstance(inferred, (nodes.List, nodes.Tuple, nodes.Set)):
        return _const_str_elements(inferred.elts)
    if isinstance(inferred, nodes.Dict):
        return _const_str_elements([key for key, _ in inferred.items])
    return None


def _enclosing_class(node: nodes.NodeNG) -> nodes.ClassDef | None:
    """Walk up the tree to find the enclosing class."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.ClassDef):
            return current
        current = current.parent
    return None


def _bases_resolved(klass: nodes.ClassDef) -> bool:
    """Return True if every base in *klass*'s full ancestry resolves to a class.

    When a base cannot be resolved its methods are invisible, so a step could
    be defined there without us seeing it -- in that case we must not flag.
    The whole chain is walked, not just the direct bases: a resolvable base
    with an unresolvable ancestor hides methods just the same.
    """
    seen: set[str] = set()
    stack: list[nodes.ClassDef] = [klass]
    while stack:
        current = stack.pop()
        if current.qname() in seen:
            continue
        seen.add(current.qname())
        for base in current.bases:
            target = base.value if isinstance(base, nodes.Subscript) else base
            inferred = _safe_infer(target)
            if not isinstance(inferred, nodes.ClassDef):
                return False
            stack.append(inferred)
    return True


def _step_handler_names(klass: nodes.ClassDef) -> set[str]:
    """Collect ``async_step_*`` handler names on *klass* and its ancestors.

    The class namespace is used rather than only method definitions, so that
    aliases (e.g. ``async_step_user = async_step_location``) -- a valid and
    used pattern -- are recognised as handlers too.
    """
    names: set[str] = set()
    for current in (klass, *extended_ancestors(klass)):
        for name in current.locals:
            if name.startswith(_STEP_PREFIX):
                names.add(name)
    return names


class HassConfigFlowMenuOptionsChecker(BaseChecker):
    """Checker for menu_options referencing missing async_step_* methods."""

    name = "home_assistant_config_flow_menu_options"
    priority = -1
    msgs = {
        "W7434": (
            "Config flow menu option '%s' has no matching `async_step_%s` "
            "method on the flow",
            "home-assistant-config-flow-menu-missing-step",
            "Used when async_show_menu is called with a menu option that does "
            "not correspond to an async_step_<option> method on the flow "
            "class. Selecting that option would raise UnknownStep at runtime.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check async_show_menu calls for unresolved menu options."""
        if (
            not isinstance(node.func, nodes.Attribute)
            or node.func.attrname != "async_show_menu"
        ):
            return

        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        menu_options = next(
            (kw.value for kw in node.keywords if kw.arg == "menu_options"), None
        )
        if menu_options is None:
            return

        step_ids = _resolve_step_ids(menu_options)
        if not step_ids:
            return

        klass = _enclosing_class(node)
        if klass is None or not _bases_resolved(klass):
            return

        step_handlers = _step_handler_names(klass)
        for step_id in sorted(step_ids):
            if f"{_STEP_PREFIX}{step_id}" not in step_handlers:
                self.add_message(
                    "home-assistant-config-flow-menu-missing-step",
                    node=menu_options,
                    args=(step_id, step_id),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassConfigFlowMenuOptionsChecker(linter))
