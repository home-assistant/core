"""Checkers for the ``entity-unique-id`` Bronze quality-scale rule.

Both checkers in this module are **quality-scale-gated**: they only
fire for integrations whose ``quality_scale.yaml`` marks
``entity-unique-id`` as ``done``.

``W7423`` (``home-assistant-missing-entity-unique-id``)
-------------------------------------------------------
Every entity class instantiated by a platform must *statically guarantee*
a non-``None`` unique id for every instance. Patterns that set the value
conditionally or per-instance work today but don't enforce the rule, so
they're rejected; integrations that need them can use
``# pylint: disable=home-assistant-missing-entity-unique-id`` after
verifying that all instantiations end up with a non-``None`` id.

Accepted paths (any one, in the class or any ancestor):

1. Class body: ``_attr_unique_id = <non-None value>`` (or
   ``_attr_unique_id: str = <non-None value>``).
2. A method body unconditionally executes ``self._attr_unique_id =
   <expr>``. The assignment is unconditional if every successful path
   through the method reaches it: either it sits at the top level of
   the body (possibly after side-effect statements or non-terminating
   control flow), or it appears in both branches of an ``if/else``.
   Early-exit guards (``if cond: return`` / ``raise``) before the
   assignment break the guarantee and are rejected.
3. Class body defines a ``unique_id`` function (typically decorated
   ``@property`` or ``@cached_property``), overriding the default that
   reads ``self._attr_unique_id``.

Mixin/base classes that are subclassed by another class in the same
module are exempted on the assumption that the subclass is the runtime
entity.

Known limitations:

- **Computed or dynamic assignment.** ``setattr(self, "_attr_unique_id",
  ...)`` and any factory or metaprogrammed path are not detected:
  static analysis can't follow them.
- **Non-literal None.** ``self._attr_unique_id = some_var`` where
  ``some_var`` happens to be ``None`` at runtime is accepted; only the
  literal ``None`` is rejected.

``W7424`` (``home-assistant-entity-unique-id-static``)
------------------------------------------------------
Entity unique IDs are scoped per ``(domain, platform)`` across **all**
config entries of the integration. A class-body string-literal
``_attr_unique_id = "..."`` therefore collides on the second config
entry of a non-singleton integration. The rule fires when:

- the class body assigns ``_attr_unique_id`` to a literal string, and
- the integration's ``manifest.json`` does **not** declare
  ``single_config_entry: true``.

To resolve: either compute the id per instance (using config-entry id,
serial, MAC, etc.), or declare the integration as
``single_config_entry`` if there is genuinely only ever one instance.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS, QualityScaleRule
from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.entity_class import (
    ENTITY_QNAME,
    collect_same_module_ancestor_qnames,
    inherits_from_entity,
)
from pylint_home_assistant.helpers.integration import read_manifest
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done

_ATTR_NAME = "_attr_unique_id"
_PROPERTY_NAME = "unique_id"


def _is_non_none_value(value: nodes.NodeNG | None) -> bool:
    """Return True if the AST value is present and not a literal ``None``."""
    if value is None:
        return False
    return not (isinstance(value, nodes.Const) and value.value is None)


def _class_body_sets_attr_non_none(class_node: nodes.ClassDef) -> bool:
    """Return True if class body assigns ``_attr_unique_id`` to a non-None value.

    The literal ``None`` is rejected, since the goal is to override the
    ``Entity._attr_unique_id = None`` default. Any other value (string
    literal, name reference, expression) is accepted.
    """
    for item in class_node.body:
        match item:
            case nodes.AnnAssign(target=nodes.AssignName(name=name), value=value) if (
                name == _ATTR_NAME and _is_non_none_value(value)
            ):
                return True
            case nodes.Assign(targets=targets, value=value) if _is_non_none_value(
                value
            ) and any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR_NAME
                for t in targets
            ):
                return True
    return False


def _class_body_nullifies_attr(class_node: nodes.ClassDef) -> bool:
    """Return True if class body explicitly assigns ``_attr_unique_id = None``."""
    for item in class_node.body:
        match item:
            case nodes.AnnAssign(
                target=nodes.AssignName(name=name),
                value=nodes.Const(value=None),
            ) if name == _ATTR_NAME:
                return True
            case nodes.Assign(
                targets=targets,
                value=nodes.Const(value=None),
            ) if any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR_NAME
                for t in targets
            ):
                return True
    return False


def _stmt_is_target_assign(stmt: nodes.NodeNG) -> bool:
    """Return True if stmt is ``self._attr_unique_id = <non-None>``.

    Accepts both ``Assign`` and ``AnnAssign``.
    """
    match stmt:
        case nodes.Assign(targets=targets, value=value):
            pass
        case nodes.AnnAssign(target=target, value=value):
            targets = [target]
        case _:
            return False
    return _is_non_none_value(value) and any(
        _is_self_attr_target(target) for target in targets
    )


def _is_self_attr_target(target: nodes.NodeNG) -> bool:
    """Return True if *target* is ``self._attr_unique_id``."""
    match target:
        case nodes.AssignAttr(attrname=name, expr=nodes.Name(name="self")) if (
            name == _ATTR_NAME
        ):
            return True
        case _:
            return False


def _stmts_contain_terminator(stmts: list[nodes.NodeNG]) -> bool:
    """Return True if any top-level or nested-If statement is a terminator.

    Recurses into ``If`` branches because an early-return guard
    (``if cond: return``) makes the assignment after it conditional.
    Does not recurse into loops, ``try``, ``with``, or nested function
    definitions: those are assumed to fall through.
    """
    for stmt in stmts:
        match stmt:
            case nodes.Return() | nodes.Raise() | nodes.Break() | nodes.Continue():
                return True
            case nodes.If(body=body, orelse=orelse) if _stmts_contain_terminator(
                body
            ) or _stmts_contain_terminator(orelse):
                return True
    return False


def _body_guarantees_target_assign(stmts: list[nodes.NodeNG]) -> bool:
    """Return True if every successful path through *stmts* reaches the target.

    Walks the statement list in order. Side-effect statements
    (``Assign``, ``Expr``, ``AugAssign``, ``Pass``, etc.) are skipped.
    Terminators (``return``/``raise``/``break``/``continue``) end the
    scan with False. For an ``If``, the target is reached if both
    branches reach it; otherwise, if either branch may terminate, the
    scan stops; otherwise the ``If`` is treated as a side-effect block
    and scanning continues.

    Loops, ``try``, ``with``, etc. are treated as fall-through (we do
    not recurse into them): a conservative direction that may miss
    some genuinely missing assignments but never produces a false
    positive for working code.
    """
    for stmt in stmts:
        if _stmt_is_target_assign(stmt):
            return True
        match stmt:
            case nodes.Return() | nodes.Raise() | nodes.Break() | nodes.Continue():
                return False
            case nodes.If(body=body, orelse=orelse):
                if (
                    _body_guarantees_target_assign(body)
                    and orelse
                    and _body_guarantees_target_assign(orelse)
                ):
                    return True
                if _stmts_contain_terminator(body) or _stmts_contain_terminator(orelse):
                    return False
        # Other statements (Assign, AnnAssign, Expr, AugAssign, Pass,
        # For, While, Try, With, FunctionDef, etc.) are treated as
        # fall-through.
    return False


def _method_unconditionally_sets_attr(class_node: nodes.ClassDef) -> bool:
    """Return True if any method in the class guarantees the target assignment."""
    return any(
        isinstance(method, nodes.FunctionDef | nodes.AsyncFunctionDef)
        and _body_guarantees_target_assign(method.body)
        for method in class_node.body
    )


def _class_defines_unique_id_method(class_node: nodes.ClassDef) -> bool:
    """Return True if the class body defines a ``unique_id`` method/property.

    ``Entity`` itself defines ``unique_id`` as a ``@cached_property`` that
    reads ``self._attr_unique_id`` (whose default is ``None``), so it
    must be excluded: otherwise every Entity subclass would trivially
    pass.
    """
    if class_node.qname() == ENTITY_QNAME:
        return False
    return any(
        isinstance(item, nodes.FunctionDef | nodes.AsyncFunctionDef)
        and item.name == _PROPERTY_NAME
        for item in class_node.body
    )


def _class_satisfies_rule(class_node: nodes.ClassDef) -> bool:
    """Return True if this single class satisfies the rule on its own.

    Checks the three runtime resolution paths against the class body
    only; ancestors are checked by the caller.
    """
    return (
        _class_body_sets_attr_non_none(class_node)
        or _method_unconditionally_sets_attr(class_node)
        or _class_defines_unique_id_method(class_node)
    )


def _unique_id_handled(class_node: nodes.ClassDef) -> bool:
    """Return True if the rule is satisfied by the class or any ancestor."""
    if _class_body_nullifies_attr(class_node):
        return False
    if _class_satisfies_rule(class_node):
        return True
    return any(
        _class_satisfies_rule(ancestor) for ancestor in extended_ancestors(class_node)
    )


def _class_body_static_string_node(
    class_node: nodes.ClassDef,
) -> nodes.NodeNG | None:
    """Return the AST node for a class-body string-literal ``_attr_unique_id``.

    Only matches ``_attr_unique_id = "..."`` / ``_attr_unique_id: str =
    "..."`` where the right-hand side is a literal ``str`` constant.
    Returns the offending node so the caller can attach a message to it;
    ``None`` if no such assignment exists.
    """
    for item in class_node.body:
        match item:
            case nodes.AnnAssign(
                target=nodes.AssignName(name=name),
                value=nodes.Const(value=str()) as value,
            ) if name == _ATTR_NAME:
                return value
            case nodes.Assign(
                targets=targets,
                value=nodes.Const(value=str()) as value,
            ) if any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR_NAME
                for t in targets
            ):
                return value
    return None


def _is_single_config_entry(module: nodes.Module) -> bool:
    """Return True if the integration's manifest declares single_config_entry."""
    manifest = read_manifest(module)
    return bool(manifest and manifest.get("single_config_entry"))


class EntityUniqueIdChecker(BaseChecker):
    """Checkers for the ``entity-unique-id`` quality-scale rule."""

    name = "home_assistant_entity_unique_id"
    priority = -1
    msgs = {
        "W7423": (
            (
                "Entity class `%s` should set `_attr_unique_id` or define a "
                "`unique_id` property "
                "(https://developers.home-assistant.io/docs/core/"
                "integration-quality-scale/rules/entity-unique-id)"
            ),
            "home-assistant-missing-entity-unique-id",
            (
                "Used when an entity class defined in a platform module does "
                "not statically guarantee a non-None unique id via a class-"
                "level _attr_unique_id assignment, an unconditional "
                "self._attr_unique_id assignment at the top of a method, or "
                "a unique_id property override. Conditional and per-instance "
                "patterns are intentionally rejected."
            ),
        ),
        "W7424": (
            (
                "Entity class `%s` sets `_attr_unique_id` to a static string "
                "at class level; unique IDs are scoped per (domain, platform) "
                "across all config entries, so this collides on the second "
                "config entry. Use a per-instance value, or declare "
                "`single_config_entry: true` in manifest.json if there is "
                "genuinely only one instance "
                "(https://developers.home-assistant.io/docs/core/"
                "integration-quality-scale/rules/entity-unique-id)"
            ),
            "home-assistant-entity-unique-id-static",
            (
                "Used when an entity class assigns _attr_unique_id to a "
                "literal string at class body in an integration that "
                "supports multiple config entries. Two instances of the "
                "class would share the same unique id and collide in the "
                "entity registry."
            ),
        ),
    }
    options = ()

    _check_module: bool
    _is_single_entry: bool
    _subclassed_qnames: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module gating result."""
        platform = get_module_platform(node.name)
        self._check_module = (
            platform is not None
            and platform in ENTITY_COMPONENTS
            and quality_scale_rule_is_done(node, QualityScaleRule.ENTITY_UNIQUE_ID)
        )
        self._is_single_entry = self._check_module and _is_single_config_entry(node)
        self._subclassed_qnames = (
            collect_same_module_ancestor_qnames(node) if self._check_module else set()
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag entity classes missing or mis-scoping ``_attr_unique_id``."""
        if not self._check_module:
            return
        # Skip mixin / abstract bases: another class in the same module
        # inherits from this one, so this class is not the runtime entity.
        if node.qname() in self._subclassed_qnames:
            return
        if not inherits_from_entity(node):
            return
        if (
            not self._is_single_entry
            and (static_node := _class_body_static_string_node(node)) is not None
        ):
            self.add_message(
                "home-assistant-entity-unique-id-static",
                node=static_node,
                args=(node.name,),
            )
            return
        if _unique_id_handled(node):
            return
        self.add_message(
            "home-assistant-missing-entity-unique-id",
            node=node,
            args=(node.name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(EntityUniqueIdChecker(linter))
