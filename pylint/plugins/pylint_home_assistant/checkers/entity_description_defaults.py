"""Checker for redundant default values in EntityDescription.

Setting an EntityDescription field to its default value is unnecessary
and adds noise. For example, ``entity_registry_enabled_default=True``
is the default and should be omitted.

Defaults are resolved dynamically from the EntityDescription class
hierarchy using astroid inference, so new fields and subclasses are
picked up automatically.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

# Only flag defaults that are simple constants (None, True, False).
# Other defaults (empty strings, 0, mutable defaults) are intentionally
# excluded because they are less likely to be set redundantly.
# Using a tuple + identity checks because 0 == False and 1 == True in
# Python, and we must not conflate integer defaults with booleans.
_FLAGGABLE_DEFAULTS = (None, True, False)


def _is_flaggable(value: object) -> bool:
    """Check if a value is a flaggable default using identity comparison."""
    return any(value is v for v in _FLAGGABLE_DEFAULTS)


# Cache: class qname -> {field_name: default_value}
_defaults_cache: dict[str, dict[str, object]] = {}


def _collect_defaults(class_node: nodes.ClassDef) -> dict[str, object]:
    """Collect flaggable default values from a class and its ancestors.

    Walks the MRO (via astroid ancestors) and collects ``AnnAssign``
    nodes that have a ``Const`` default in ``_FLAGGABLE_DEFAULTS``.
    Child class defaults override parent defaults.

    When a subclass overrides a field with a non-flaggable or non-Const
    default (e.g., ``entity_category = EntityCategory.DIAGNOSTIC``), the
    field is removed from the result so we do not incorrectly flag
    instances that set it back to a parent's default value.
    """
    qname = class_node.qname()
    if qname in _defaults_cache:
        return _defaults_cache[qname]

    # Collect from ancestors in reverse MRO order (most distant first)
    # so closer ancestors overwrite, then the class itself wins last.
    defaults: dict[str, object] = {}

    try:
        ancestors = list(class_node.ancestors())
    except astroid.exceptions.InferenceError:
        ancestors = []

    for ancestor in reversed(ancestors):
        _update_defaults(defaults, ancestor)

    # The class itself overrides all ancestors
    _update_defaults(defaults, class_node)

    _defaults_cache[qname] = defaults
    return defaults


def _update_defaults(defaults: dict[str, object], class_node: nodes.ClassDef) -> None:
    """Update defaults dict from a single class body.

    Flaggable Const defaults are added. Any field that is redefined with
    a non-flaggable value (non-Const or a Const outside the flaggable set)
    is removed so that parent defaults do not leak through.
    """
    for item in class_node.body:
        if not isinstance(item, nodes.AnnAssign):
            continue
        if not isinstance(item.target, nodes.AssignName):
            continue
        if item.value is None:
            # Annotation-only (no default), leave existing entry untouched
            continue

        name = item.target.name
        if isinstance(item.value, nodes.Const) and _is_flaggable(item.value.value):
            defaults[name] = item.value.value
        else:
            # Subclass overrides with a non-flaggable value; remove
            # so we don't flag instances using the parent's default.
            defaults.pop(name, None)


_ENTITY_DESCRIPTION_QNAME = "homeassistant.helpers.entity.EntityDescription"


def _is_entity_description(class_node: nodes.ClassDef) -> bool:
    """Check if a class is or inherits from EntityDescription."""
    if class_node.qname() == _ENTITY_DESCRIPTION_QNAME:
        return True
    try:
        return any(
            ancestor.qname() == _ENTITY_DESCRIPTION_QNAME
            for ancestor in class_node.ancestors()
        )
    except astroid.exceptions.InferenceError:
        return False


def _resolve_description_class(call: nodes.Call) -> nodes.ClassDef | None:
    """Resolve the EntityDescription subclass from a constructor call."""
    try:
        for inferred in call.func.infer():
            if isinstance(inferred, nodes.ClassDef) and _is_entity_description(
                inferred
            ):
                return inferred
    except astroid.exceptions.InferenceError:
        pass
    return None


class EntityDescriptionDefaultsChecker(BaseChecker):
    """Checker for redundant default values in EntityDescription."""

    name = "home_assistant_entity_description_defaults"
    priority = -1
    msgs = {
        "C7412": (
            "Setting `%s=%s` is redundant, it is already the default",
            "home-assistant-entity-description-redundant-default",
            "Used when an EntityDescription sets a field to its default "
            "value. Remove the argument to reduce noise.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Check EntityDescription calls for redundant defaults."""
        if not self._in_integration:
            return

        # Skip calls without keyword arguments (nothing to check)
        if not node.keywords:
            return

        # For attribute calls (obj.attr()), only proceed if the attribute
        # name contains "Description" (e.g., module.SensorEntityDescription()).
        # This skips the vast majority of method calls (self.method(),
        # hass.async_create_task()) while catching module-qualified
        # constructors. Plain Name calls always proceed to support aliases.
        if (
            isinstance(node.func, nodes.Attribute)
            and "Description" not in node.func.attrname
        ):
            return

        class_node = _resolve_description_class(node)
        if class_node is None:
            return

        defaults = _collect_defaults(class_node)
        if not defaults:
            return

        for kw in node.keywords:
            if kw.arg not in defaults:
                continue

            if not isinstance(kw.value, nodes.Const):
                continue

            default = defaults[kw.arg]
            if kw.value.value is default:
                self.add_message(
                    "home-assistant-entity-description-redundant-default",
                    node=kw,
                    args=(kw.arg, repr(default)),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(EntityDescriptionDefaultsChecker(linter))
