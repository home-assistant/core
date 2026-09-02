"""Checker for light entities that report only one of the color-mode attributes.

A ``LightEntity`` must report **both** ``supported_color_modes`` and
a current ``color_mode``; setting one without the other raises
``HomeAssistantError`` at runtime. These two checks flag each half of that
inconsistency. A light that sets *neither* is deliberately not flagged: the
realistic both-missing class is an abstract base (which the concrete
subclass completes), so flagging it would produce false positives — the
tradeoff is that a concrete both-missing light, which also raises at
runtime, is not caught.

A value is considered *provided* by a class when its effective declaration,
resolved in MRO order and excluding ``LightEntity``'s own ``None`` defaults,
is one of:

- a non-``None`` class-body ``_attr_...`` assignment,
- a ``self._attr_... = ...`` assignment in a method body, or
- a property/method override of the public name.

Subclass shadowing is respected: a subclass that assigns the ``_attr_...``
to ``None`` nullifies a non-``None`` value inherited from an ancestor, so
the pair is treated as unset from that subclass down.

Mixin/abstract bases that are subclassed by another class in the same
module are exempted, on the assumption that the concrete subclass is the
runtime entity (and may supply the missing half itself).

``W7436`` (``home-assistant-light-missing-color-mode``)
-------------------------------------------------------
Fires when ``supported_color_modes`` is provided but ``color_mode`` is not.
At runtime ``LightEntity.state_attributes`` raises ``HomeAssistantError``
("does not report a color mode") whenever the light is on and
``color_mode`` is ``None`` — there is no inference of the mode from a
single supported mode, so this holds even for lights that support only
``ONOFF`` or ``BRIGHTNESS``.

``W7437`` (``home-assistant-light-missing-supported-color-modes``)
------------------------------------------------------------------
Fires when ``color_mode`` is provided but ``supported_color_modes`` is not.
At runtime ``LightEntity._light_internal_supported_color_modes`` raises
``HomeAssistantError`` ("does not set supported color modes") from both
``state_attributes`` and ``capability_attributes`` whenever
``supported_color_modes`` is ``None``.

Known limitations:

- A base defined in one module whose missing half is only supplied by
  subclasses in a *different* module is flagged, because the subclasses are
  not visible when the base's module is linted. Suppress with a
  ``# pylint: disable=...`` on the base.
- A property override is treated as providing the value regardless of what
  it returns; a property that returns ``None`` at runtime is the
  integration's responsibility.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.entity_class import (
    LIGHT_ENTITY_QNAME,
    collect_same_module_ancestor_qnames,
    inherits_from_light_entity,
)
from pylint_home_assistant.helpers.module_info import is_integration_module

_SUPPORTED_ATTR = "_attr_supported_color_modes"
_SUPPORTED_PROPERTY = "supported_color_modes"
_COLOR_MODE_ATTR = "_attr_color_mode"
_COLOR_MODE_PROPERTY = "color_mode"


def _is_non_none_value(value: nodes.NodeNG | None) -> bool:
    """Return True if the AST value is present and not a literal ``None``."""
    if value is None:
        return False
    return not (isinstance(value, nodes.Const) and value.value is None)


def _is_self_attr_target(target: nodes.NodeNG, attr_name: str) -> bool:
    """Return True if *target* is ``self.<attr_name>``."""
    match target:
        case nodes.AssignAttr(attrname=name, expr=nodes.Name(name="self")) if (
            name == attr_name
        ):
            return True
    return False


def _class_body_attr_state(class_node: nodes.ClassDef, attr_name: str) -> bool | None:
    """Return the effect of the class body's final assignment to *attr_name*.

    ``True`` if the last source-order assignment sets a non-``None`` value,
    ``False`` if it sets a literal ``None``, or ``None`` if the class body
    does not assign *attr_name* at all. Later assignments win, matching
    Python's class-body evaluation, so ``x = ColorMode.HS`` followed by
    ``x = None`` resolves to ``False``. Annotation-only statements (``x: T``
    with no value) are not assignments and are ignored.
    """
    state: bool | None = None
    for item in class_node.body:
        match item:
            case nodes.AnnAssign(target=nodes.AssignName(name=name), value=value) if (
                name == attr_name and value is not None
            ):
                state = _is_non_none_value(value)
            case nodes.Assign(targets=targets, value=value) if any(
                isinstance(t, nodes.AssignName) and t.name == attr_name for t in targets
            ):
                state = _is_non_none_value(value)
    return state


def _method_sets_self_attr(class_node: nodes.ClassDef, attr_name: str) -> bool:
    """Return True if any method assigns ``self.<attr_name> = <non-None>``.

    The assignment need not be unconditional: any assignment means the class
    reports the attribute and must therefore also report the paired value.
    Assignments in nested functions or classes (which have their own
    ``self``) are ignored — only the method's own scope counts.
    """
    for method in class_node.body:
        if not isinstance(method, nodes.FunctionDef | nodes.AsyncFunctionDef):
            continue
        for stmt in method.nodes_of_class((nodes.Assign, nodes.AnnAssign)):
            if stmt.scope() is not method:
                continue
            match stmt:
                case nodes.Assign(targets=targets, value=value):
                    target_list = list(targets)
                case nodes.AnnAssign(target=target, value=value):
                    target_list = [target]
                case _:
                    continue
            if _is_non_none_value(value) and any(
                _is_self_attr_target(t, attr_name) for t in target_list
            ):
                return True
    return False


def _class_defines_method(class_node: nodes.ClassDef, method_name: str) -> bool:
    """Return True if the class body overrides *method_name* (property/method)."""
    return any(
        isinstance(item, nodes.FunctionDef | nodes.AsyncFunctionDef)
        and item.name == method_name
        for item in class_node.body
    )


def _class_declaration(
    class_node: nodes.ClassDef, attr_name: str, property_name: str
) -> bool | None:
    """Return this class's *effective* declaration for the attr/property.

    ``True`` if the class provides a value, ``False`` if it nullifies an
    inherited value (class-body ``_attr_... = None``), or ``None`` if the
    class does not declare the pair at all. ``LightEntity`` declares the
    ``None`` defaults, so it resolves to ``False`` — reaching it means no
    subclass provided a value.

    Precedence within the class follows runtime resolution: a
    ``property``/method override or a non-``None`` ``self._attr_...``
    assignment wins over a class-body ``_attr_... = None``.
    """
    if class_node.qname() == LIGHT_ENTITY_QNAME:
        return False
    if _class_defines_method(class_node, property_name):
        return True
    if _method_sets_self_attr(class_node, attr_name):
        return True
    return _class_body_attr_state(class_node, attr_name)


def _mro(class_node: nodes.ClassDef) -> list[nodes.ClassDef]:
    """Return the class's MRO, falling back to a DFS ancestor walk."""
    try:
        return class_node.mro()  # type: ignore[no-any-return]
    except astroid.exceptions.MroError:
        return [class_node, *extended_ancestors(class_node)]


def _provides_effective(
    class_node: nodes.ClassDef, attr_name: str, property_name: str
) -> bool:
    """Return True if the effective value for *class_node* is provided.

    Walks the MRO most-derived first and returns the first class that
    declares the pair, so a subclass ``_attr_... = None`` shadows a
    non-``None`` value set by an ancestor.
    """
    for klass in _mro(class_node):
        decl = _class_declaration(klass, attr_name, property_name)
        if decl is not None:
            return decl
    return False


class HassLightColorModeChecker(BaseChecker):
    """Flag light entities that report only one of the color-mode attributes."""

    name = "home_assistant_light_color_mode"
    priority = -1
    msgs = {
        "W7436": (
            (
                "Light entity class `%s` reports supported color modes but "
                "does not report a color mode; set `_attr_color_mode` or "
                "override the `color_mode` property"
            ),
            "home-assistant-light-missing-color-mode",
            (
                "Used when a LightEntity subclass provides "
                "supported_color_modes (via _attr_supported_color_modes or a "
                "supported_color_modes override) but neither sets "
                "_attr_color_mode nor overrides the color_mode property. Such "
                "a light raises HomeAssistantError at runtime because it does "
                "not report a color mode when turned on."
            ),
        ),
        "W7437": (
            (
                "Light entity class `%s` reports a color mode but does not "
                "report supported color modes; set "
                "`_attr_supported_color_modes` or override the "
                "`supported_color_modes` property"
            ),
            "home-assistant-light-missing-supported-color-modes",
            (
                "Used when a LightEntity subclass provides color_mode (via "
                "_attr_color_mode or a color_mode override) but neither sets "
                "_attr_supported_color_modes nor overrides the "
                "supported_color_modes property. Such a light raises "
                "HomeAssistantError at runtime because it does not set "
                "supported color modes."
            ),
        ),
    }
    options = ()

    _check_module: bool
    _subclassed_qnames: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module state."""
        self._check_module = is_integration_module(node.name)
        self._subclassed_qnames = (
            collect_same_module_ancestor_qnames(node) if self._check_module else set()
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag light entities reporting only one of the color-mode attributes."""
        if not self._check_module:
            return
        # Skip mixin / abstract bases: another class in the same module
        # inherits from this one, so this class is not the runtime entity.
        if node.qname() in self._subclassed_qnames:
            return
        if not inherits_from_light_entity(node):
            return
        provides_supported = _provides_effective(
            node, _SUPPORTED_ATTR, _SUPPORTED_PROPERTY
        )
        provides_color_mode = _provides_effective(
            node, _COLOR_MODE_ATTR, _COLOR_MODE_PROPERTY
        )
        # Only the XOR is flagged: reporting both is correct, and reporting
        # neither is skipped to avoid false positives on abstract bases (a
        # concrete both-missing light also raises but is not caught).
        if provides_supported and not provides_color_mode:
            self.add_message(
                "home-assistant-light-missing-color-mode",
                node=node,
                args=(node.name,),
            )
        elif provides_color_mode and not provides_supported:
            self.add_message(
                "home-assistant-light-missing-supported-color-modes",
                node=node,
                args=(node.name,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassLightColorModeChecker(linter))
