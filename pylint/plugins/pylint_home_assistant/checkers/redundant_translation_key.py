"""Checker for a ``translation_key`` that only repeats the device class name.

Entities on some platforms, such as sensors, are named after their device
class when they have no name of their own. The name comes from
``entity_component.<device_class>.name`` in the platform's ``strings.json``.

An ``EntityDescription``, or an entity class through ``_attr_device_class``
and ``_attr_translation_key``, that sets both a device class and a
translation key whose name translates to that same string adds nothing.
When the translation key is used for nothing else, remove it. When it also
holds states, state attributes or icons, or the integration's code reads it,
remove only its name.

``W7442`` (``home-assistant-redundant-translation-key``)
"""

from functools import cache
from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import resolve_entity_description_class
from pylint_home_assistant.helpers.icons import load_icons
from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import (
    is_integration_module,
    parse_module,
)
from pylint_home_assistant.helpers.translations import (
    load_translations,
    load_translations_for_domain,
    resolve_translation_reference,
)

# Platforms whose entities fall back to the device class name, see their
# ``_default_to_device_class_name``. Other platforms, such as switch, would
# lose the entity name without the translation key.
_PLATFORMS_NAMED_BY_DEVICE_CLASS = frozenset(
    {"binary_sensor", "button", "event", "number", "sensor", "update"}
)

# Sensors with this device class don't fall back to the device class name
_SENSOR_ENUM_DEVICE_CLASS = "enum"


@cache
def _code_reads_translation_key(integration_dir: Path) -> bool:
    """Return True if the integration's code reads a ``translation_key``.

    Such code, for example ``f"{description.translation_key}_n"``, may rely on
    the key being set.
    """
    for source in integration_dir.rglob("*.py"):
        try:
            module = astroid.parse(source.read_text())
        except astroid.exceptions.AstroidSyntaxError, OSError:
            continue
        for attribute in module.nodes_of_class(nodes.Attribute):
            if attribute.attrname == "translation_key":
                return True
    return False


def _resolve_string(node: nodes.NodeNG) -> str | None:
    """Return the string *node* holds or infers to.

    Enum members, such as ``SensorDeviceClass.POWER``, resolve to their value.
    """
    match node:
        case nodes.Const(value=str() as value):
            return value

    try:
        for inferred in node.infer():
            match inferred:
                case nodes.Const(value=str() as value):
                    return value
                case astroid.Instance():
                    for member_value in inferred.igetattr("value"):
                        match member_value:
                            case nodes.Const(value=str() as value):
                                return value
    except astroid.exceptions.InferenceError, StopIteration:
        pass

    return None


class RedundantTranslationKeyChecker(BaseChecker):
    """Checker for a translation_key that only repeats the device class name."""

    name = "home_assistant_redundant_translation_key"
    priority = -1
    msgs = {
        "W7442": (
            (
                "The name of translation_key '%s' is the same as the name of "
                "device class '%s' (\"%s\"); %s"
            ),
            "home-assistant-redundant-translation-key",
            (
                "Used when an entity description or entity class sets a "
                "translation_key whose name is the same as the name its device "
                "class already provides. Remove the translation_key, or only "
                "its name when the key is also used for states, state "
                "attributes, icons or in code."
            ),
        ),
    }
    options = ()

    _platform: str | None = None
    _module: nodes.Module | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Record the platform if the module belongs to one we check."""
        self._platform = None
        self._module = None
        if not is_integration_module(node.name):
            return

        parsed = parse_module(node.name)
        if parsed is not None and parsed.module in _PLATFORMS_NAMED_BY_DEVICE_CLASS:
            self._platform = parsed.module
            self._module = node

    def visit_call(self, node: nodes.Call) -> None:
        """Check entity descriptions that set a device class and translation key."""
        if self._platform is None or self._module is None or not node.keywords:
            return

        keywords = {keyword.arg: keyword for keyword in node.keywords}
        translation_key_keyword = keywords.get("translation_key")
        device_class_keyword = keywords.get("device_class")
        if (
            translation_key_keyword is None
            or device_class_keyword is None
            or resolve_entity_description_class(node) is None
        ):
            return

        self._check(
            translation_key_keyword,
            translation_key_keyword.value,
            device_class_keyword.value,
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check entity classes that set a device class and translation key."""
        if self._platform is None or self._module is None:
            return

        values: dict[str, nodes.Assign] = {}
        for item in node.body:
            match item:
                case nodes.Assign(
                    targets=[
                        nodes.AssignName(
                            name="_attr_translation_key" | "_attr_device_class" as name
                        )
                    ]
                ):
                    values[name] = item
        if (translation_key_assign := values.get("_attr_translation_key")) is None or (
            device_class_assign := values.get("_attr_device_class")
        ) is None:
            return

        self._check(
            translation_key_assign,
            translation_key_assign.value,
            device_class_assign.value,
        )

    def _check(
        self,
        report_node: nodes.NodeNG,
        translation_key_node: nodes.NodeNG,
        device_class_node: nodes.NodeNG,
    ) -> None:
        """Flag *report_node* if the translation key repeats the device class name."""
        translation_key = _resolve_string(translation_key_node)
        device_class = _resolve_string(device_class_node)
        if (
            translation_key is None
            or device_class is None
            or (
                self._platform == "sensor" and device_class == _SENSOR_ENUM_DEVICE_CLASS
            )
        ):
            return

        if (name := self._redundant_name(translation_key, device_class)) is not None:
            self.add_message(
                "home-assistant-redundant-translation-key",
                node=report_node,
                args=(
                    translation_key,
                    device_class,
                    name,
                    self._advice(translation_key),
                ),
            )

    def _redundant_name(self, translation_key: str, device_class: str) -> str | None:
        """Return the name if the translation key repeats the device class name."""
        assert self._platform is not None
        assert self._module is not None

        entity_translation = (
            (load_translations(self._module) or {})
            .get("entity", {})
            .get(self._platform, {})
            .get(translation_key)
        )
        device_class_translation = (
            (load_translations_for_domain(self._module, self._platform) or {})
            .get("entity_component", {})
            .get(device_class)
        )
        if not isinstance(entity_translation, dict) or not isinstance(
            device_class_translation, dict
        ):
            return None

        entity_name = entity_translation.get("name")
        device_class_name = device_class_translation.get("name")
        if not isinstance(entity_name, str) or not isinstance(device_class_name, str):
            return None

        integration_dir = get_integration_dir(self._module)
        components_dir = integration_dir.parent if integration_dir else None
        entity_name = resolve_translation_reference(entity_name, components_dir)
        device_class_name = resolve_translation_reference(
            device_class_name, components_dir
        )
        return entity_name if entity_name == device_class_name else None

    def _advice(self, translation_key: str) -> str:
        """Return what to remove: the whole key, or only its name."""
        assert self._platform is not None
        assert self._module is not None

        entity_translation = (
            (load_translations(self._module) or {})
            .get("entity", {})
            .get(self._platform, {})
            .get(translation_key, {})
        )
        entity_icons = (
            (load_icons(self._module) or {})
            .get("entity", {})
            .get(self._platform, {})
            .get(translation_key)
        )
        integration_dir = get_integration_dir(self._module)
        if (
            set(entity_translation) - {"name"}
            or entity_icons
            or (integration_dir and _code_reads_translation_key(integration_dir))
        ):
            return (
                "remove only its name from strings.json, the key is also used "
                "for states, state attributes, icons or in code"
            )
        return "remove the translation_key and its strings.json entry"


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantTranslationKeyChecker(linter))
