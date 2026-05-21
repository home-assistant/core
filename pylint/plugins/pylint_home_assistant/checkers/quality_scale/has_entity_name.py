"""Checker for missing ``_attr_has_entity_name`` on entity classes.

**Quality-scale-gated** (Bronze): only fires for integrations whose
``quality_scale.yaml`` marks ``has-entity-name`` as ``done``.

Every entity class instantiated by a platform must *statically guarantee*
``has_entity_name=True`` for every instance. Patterns that set the flag
conditionally or per-instance work today but don't enforce the rule, so
they're rejected; integrations that need them can use
``# pylint: disable=home-assistant-missing-has-entity-name`` after
verifying that all instantiations end up True.

Accepted paths (any one, in the class or any ancestor):

1. Class body: ``_attr_has_entity_name = True`` (or
   ``_attr_has_entity_name: bool = True``).
2. Top-level statement of a method body: ``self._attr_has_entity_name = True``.
   Must be the literal value ``True`` and must NOT be nested inside
   ``if``/``for``/``try``/etc. — that ensures it runs on every instance.
3. Class-level annotation ``entity_description: SomeDescription`` whose
   description class (or an ancestor) sets ``has_entity_name = True``
   as a class-level default.
Mixin/base classes that are subclassed by another class in the same
module are exempted on the assumption that the subclass is the runtime
entity.

Known limitations
-----------------
The rule is a high-signal heuristic, not a soundness proof. Two
intentional scope choices to be aware of:

- **Per-instance override.** When an EntityDescription subclass sets a
  class-level ``has_entity_name = True`` default, a specific instance
  can still be constructed with ``has_entity_name=False``. We accept
  based on the class default and do not scan call sites.
- **Computed or dynamic assignment.** ``@property has_entity_name``,
  ``setattr(self, "_attr_has_entity_name", ...)``, and any factory or
  metaprogrammed path are not detected — static analysis can't follow
  them.

``# pylint: disable=home-assistant-missing-has-entity-name`` on the
offending class declaration is the recommended escape hatch.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name
"""

from collections.abc import Iterator

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done

_ENTITY_QNAME = "homeassistant.helpers.entity.Entity"
_ENTITY_DESCRIPTION_QNAME = "homeassistant.helpers.entity.EntityDescription"
_ATTR_NAME = "_attr_has_entity_name"
_DESCRIPTION_ATTR = "entity_description"
_DESCRIPTION_FIELD = "has_entity_name"


def _safe_ancestors(class_node: nodes.ClassDef) -> list[nodes.ClassDef]:
    """Return ``class_node.ancestors()`` swallowing inference errors."""
    try:
        return list(class_node.ancestors())
    except astroid.exceptions.InferenceError:
        return []


def _subscript_base_classes(class_node: nodes.ClassDef) -> Iterator[nodes.ClassDef]:
    """Yield ClassDefs from subscript bases (e.g. ``class B(Base[T])``).

    astroid's ``ancestors()`` drops Subscript bases such as
    ``VeSyncBaseEntity[VeSyncFanBase | VeSyncPurifier]`` (PEP-695 generic
    syntax), so this method recovers them by inferring the subscript's
    value.
    """
    for base in class_node.bases:
        if not isinstance(base, nodes.Subscript):
            continue
        try:
            inferred = list(base.value.infer())
        except astroid.exceptions.InferenceError:
            continue
        for inferred_node in inferred:
            if isinstance(inferred_node, nodes.ClassDef):
                yield inferred_node


def _extended_ancestors(class_node: nodes.ClassDef) -> Iterator[nodes.ClassDef]:
    """Yield all ancestors including transitive subscript-based ones."""
    seen: set[str] = set()
    stack: list[nodes.ClassDef] = [class_node]

    while stack:
        current = stack.pop()
        for ancestor in _safe_ancestors(current):
            qname = ancestor.qname()
            if qname in seen:
                continue
            seen.add(qname)
            yield ancestor
            stack.append(ancestor)
        for subscript_base in _subscript_base_classes(current):
            qname = subscript_base.qname()
            if qname in seen:
                continue
            seen.add(qname)
            yield subscript_base
            stack.append(subscript_base)


def _inherits_from_entity(class_node: nodes.ClassDef) -> bool:
    """Return True if class inherits from homeassistant.helpers.entity.Entity."""
    return any(a.qname() == _ENTITY_QNAME for a in _extended_ancestors(class_node))


def _class_body_sets_attr_true(class_node: nodes.ClassDef, attr_name: str) -> bool:
    """Return True if class body assigns ``attr_name = True``.

    Limitation: only literal ``Const(True)`` values are recognised.
    ``dataclasses.field(default=True)`` and other ``Call``-shaped defaults
    are not detected even though they evaluate to True at runtime.
    """
    for item in class_node.body:
        if (
            isinstance(item, nodes.Assign)
            and any(
                isinstance(target, nodes.AssignName) and target.name == attr_name
                for target in item.targets
            )
            and isinstance(item.value, nodes.Const)
            and item.value.value is True
        ):
            return True
        if (
            isinstance(item, nodes.AnnAssign)
            and isinstance(item.target, nodes.AssignName)
            and item.target.name == attr_name
            and isinstance(item.value, nodes.Const)
            and item.value.value is True
        ):
            return True
    return False


def _method_unconditionally_sets_attr_true(class_node: nodes.ClassDef) -> bool:
    """Return True if a method unconditionally sets self._attr_has_entity_name=True.

    Accepts both ``self._attr_has_entity_name = True`` (``Assign``) and
    ``self._attr_has_entity_name: bool = True`` (``AnnAssign``). The
    assignment must:

    - have the literal value ``True``,
    - be a direct statement of the method body (not nested in
      ``if``/``for``/``try``/etc.), and
    - be preceded only by flow-safe statements (other assignments,
      ``super()`` and other expression calls, ``pass``). Any statement
      that could divert control flow (``return``, ``raise``, ``if``,
      loops, ``try``, ``assert``, etc.) before the assignment ends the
      scan, since after that point the assignment is no longer
      guaranteed to run.
    """
    for method in class_node.body:
        if not isinstance(method, nodes.FunctionDef | nodes.AsyncFunctionDef):
            continue
        for stmt in method.body:
            if isinstance(stmt, nodes.Assign):
                targets = stmt.targets
                value = stmt.value
            elif isinstance(stmt, nodes.AnnAssign):
                targets = [stmt.target]
                value = stmt.value
            elif isinstance(stmt, nodes.Expr | nodes.AugAssign | nodes.Pass):
                # Flow-safe; keep scanning past it.
                continue
            else:
                # Control-flow statement (Return/Raise/If/For/While/Try/
                # Assert/etc.); the target assignment after this point
                # is no longer guaranteed to run.
                break
            if not (isinstance(value, nodes.Const) and value.value is True):
                continue
            for target in targets:
                if (
                    isinstance(target, nodes.AssignAttr)
                    and target.attrname == _ATTR_NAME
                    and isinstance(target.expr, nodes.Name)
                    and target.expr.name == "self"
                ):
                    return True
    return False


def _is_entity_description(class_node: nodes.ClassDef) -> bool:
    """Return True if class is or inherits from EntityDescription."""
    if class_node.qname() == _ENTITY_DESCRIPTION_QNAME:
        return True
    return any(
        ancestor.qname() == _ENTITY_DESCRIPTION_QNAME
        for ancestor in _safe_ancestors(class_node)
    )


def _description_sets_has_entity_name(description_class: nodes.ClassDef) -> bool:
    """Return True if the description class or any ancestor sets has_entity_name = True."""
    if _class_body_sets_attr_true(description_class, _DESCRIPTION_FIELD):
        return True
    return any(
        _class_body_sets_attr_true(ancestor, _DESCRIPTION_FIELD)
        for ancestor in _safe_ancestors(description_class)
    )


def _entity_description_annotation_satisfies(class_node: nodes.ClassDef) -> bool:
    """Return True if a typed entity_description supplies has_entity_name=True.

    The class must declare an ``entity_description: SomeDescription``
    annotation, and that description class (or an ancestor) must set
    ``has_entity_name = True`` as a class-level default. This detects
    the ``EntityDescription.has_entity_name`` fallback path used by
    integrations like unifi, where the entity itself sets neither
    ``_attr_has_entity_name`` nor ``self._attr_has_entity_name`` but
    the typed description class supplies a True default.
    """
    for item in class_node.body:
        if not isinstance(item, nodes.AnnAssign):
            continue
        if not isinstance(item.target, nodes.AssignName):
            continue
        if item.target.name != _DESCRIPTION_ATTR:
            continue
        annotation = item.annotation
        if isinstance(annotation, nodes.Subscript):
            annotation = annotation.value
        try:
            inferred = list(annotation.infer())
        except astroid.exceptions.InferenceError:
            continue
        for inferred_node in inferred:
            if (
                isinstance(inferred_node, nodes.ClassDef)
                and _is_entity_description(inferred_node)
                and _description_sets_has_entity_name(inferred_node)
            ):
                return True
    return False


def _class_satisfies_rule(class_node: nodes.ClassDef) -> bool:
    """Return True if this single class satisfies the rule on its own.

    Checks the three runtime resolution paths against the class body
    only — ancestors are checked by the caller.
    """
    return (
        _class_body_sets_attr_true(class_node, _ATTR_NAME)
        or _method_unconditionally_sets_attr_true(class_node)
        or _entity_description_annotation_satisfies(class_node)
    )


def _has_entity_name_handled(class_node: nodes.ClassDef) -> bool:
    """Return True if the rule is satisfied by the class or any ancestor."""
    if _class_satisfies_rule(class_node):
        return True
    return any(
        _class_satisfies_rule(ancestor) for ancestor in _extended_ancestors(class_node)
    )


def _collect_same_module_ancestor_qnames(module: nodes.Module) -> set[str]:
    """Return qnames of every class used as an ancestor by any class in *module*.

    Used to exempt mixin/abstract bases from the rule. Three limitations
    fall out of the "same-module" scoping:

    1. A class that is BOTH a same-module base AND directly instantiated
       (e.g. both the base and a subclass passed to async_add_entities)
       is exempted by this filter.
    2. A base defined here but only subclassed from a *different* module
       (e.g. base in sensor.py, subclasses in binary_sensor.py) is NOT
       exempted and would be flagged as if it were a runtime entity.
    3. An abstract-by-convention class with no same-module subclass at
       all is flagged. This rule should be disable for those classes
       after verifying the class is never instantiated.
    """
    qnames: set[str] = set()
    for class_node in module.nodes_of_class(nodes.ClassDef):
        for ancestor in _extended_ancestors(class_node):
            qnames.add(ancestor.qname())
    return qnames


class HasEntityNameChecker(BaseChecker):
    """Checker for missing ``_attr_has_entity_name`` on entity classes."""

    name = "home_assistant_has_entity_name"
    priority = -1
    msgs = {
        "W7416": (
            (
                "Entity class `%s` should set `_attr_has_entity_name = True` "
                "(https://developers.home-assistant.io/docs/core/"
                "integration-quality-scale/rules/has-entity-name)"
            ),
            "home-assistant-missing-has-entity-name",
            (
                "Used when an entity class defined in a platform module does "
                "not statically guarantee has_entity_name=True via a class-"
                "level _attr_has_entity_name = True, an unconditional "
                "self._attr_has_entity_name = True at the top of a method, or "
                "an entity_description annotation whose description class "
                "sets has_entity_name = True as a default. Conditional and "
                "per-instance patterns are intentionally rejected."
            ),
        ),
    }
    options = ()

    _check_module: bool
    _subclassed_qnames: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module gating result."""
        platform = get_module_platform(node.name)
        self._check_module = (
            platform is not None
            and platform in ENTITY_COMPONENTS
            and quality_scale_rule_is_done(node, QualityScaleRule.HAS_ENTITY_NAME)
        )
        self._subclassed_qnames = (
            _collect_same_module_ancestor_qnames(node) if self._check_module else set()
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag entity classes missing _attr_has_entity_name."""
        if not self._check_module:
            return
        if not _inherits_from_entity(node):
            return
        if _has_entity_name_handled(node):
            return
        # Skip mixin / abstract bases: another class in the same module
        # inherits from this one, so this class is not the runtime entity.
        if node.qname() in self._subclassed_qnames:
            return
        self.add_message(
            "home-assistant-missing-has-entity-name",
            node=node,
            args=(node.name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HasEntityNameChecker(linter))
