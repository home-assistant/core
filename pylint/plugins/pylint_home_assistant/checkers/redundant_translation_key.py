"""Checker for redundant ``translation_key`` when ``device_class`` is set.

When an entity has a ``device_class``, Home Assistant automatically
provides a translated name from the platform's device class translations
(``entity_component.<device_class>.name`` in the platform's
``strings.json``).

Setting ``translation_key`` to a value that resolves to the same
translated name is redundant and should be removed.

``W7428`` (``home-assistant-redundant-translation-key``)
"""

import contextlib
from pathlib import Path

import astroid
from astroid import nodes
import orjson
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import (
    is_integration_module,
    parse_module,
)
from pylint_home_assistant.helpers.translations import (
    load_translations,
    resolve_translation_reference,
)

_InferenceError = astroid.exceptions.InferenceError

_ENTITY_DESCRIPTION_QNAME = "homeassistant.helpers.entity.EntityDescription"

_PLATFORMS_WITH_DEVICE_CLASS_TRANSLATIONS = frozenset(
    {
        "sensor",
        "binary_sensor",
        "number",
        "cover",
        "switch",
        "button",
        "event",
        "humidifier",
        "media_player",
    }
)

_device_class_translations_cache: dict[str, dict[str, str]] = {}


def clear_device_class_cache() -> None:
    """Clear the device class translations cache (used by tests)."""
    _device_class_translations_cache.clear()


def _load_device_class_translations(
    module: nodes.Module, platform: str
) -> dict[str, str]:
    """Load device class translations for a platform.

    Returns a dict mapping device class value to its translated name.
    """
    if platform in _device_class_translations_cache:
        return _device_class_translations_cache[platform]

    result: dict[str, str] = {}
    integration_dir = get_integration_dir(module)
    if integration_dir is not None:
        components_dir = integration_dir.parent
        platform_strings = components_dir / platform / "strings.json"
        if platform_strings.exists():
            with contextlib.suppress(orjson.JSONDecodeError, OSError):
                parsed = orjson.loads(platform_strings.read_bytes())
                if isinstance(parsed, dict):
                    entity_component = parsed.get("entity_component", {})
                    for dc_key, dc_data in entity_component.items():
                        if dc_key == "_" or not isinstance(dc_data, dict):
                            continue
                        name = dc_data.get("name")
                        if isinstance(name, str):
                            result[dc_key] = name

    _device_class_translations_cache[platform] = result
    return result


def _resolve_const_string(node: nodes.NodeNG) -> str | None:
    """Resolve a node to a constant string value."""
    match node:
        case nodes.Const(value=str() as value):
            return value

    try:
        for inferred in node.infer():
            match inferred:
                case nodes.Const(value=str() as value):
                    return value
    except _InferenceError:
        pass

    return None


def _resolve_device_class_value(node: nodes.NodeNG) -> str | None:
    """Resolve a device_class keyword value to its string form.

    Handles ``SensorDeviceClass.POWER`` style enum references by
    accessing the ``.value`` attribute on the inferred enum instance.
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
                    for val in inferred.igetattr("value"):
                        match val:
                            case nodes.Const(value=str() as value):
                                return value
    except _InferenceError, StopIteration:
        pass

    return None


def _is_entity_description(class_node: nodes.ClassDef) -> bool:
    """Check if a class is or inherits from EntityDescription."""
    if class_node.qname() == _ENTITY_DESCRIPTION_QNAME:
        return True
    try:
        return any(
            ancestor.qname() == _ENTITY_DESCRIPTION_QNAME
            for ancestor in class_node.ancestors()
        )
    except _InferenceError:
        return False


def _resolve_description_class(call: nodes.Call) -> nodes.ClassDef | None:
    """Resolve the EntityDescription subclass from a constructor call."""
    try:
        for inferred in call.func.infer():
            match inferred:
                case nodes.ClassDef() if _is_entity_description(inferred):
                    return inferred
    except _InferenceError:
        pass
    return None


class RedundantTranslationKeyChecker(BaseChecker):
    """Checker for redundant translation_key when device_class is set."""

    name = "home_assistant_redundant_translation_key"
    priority = -1
    msgs = {
        "W7428": (
            "translation_key '%s' is redundant because device_class '%s' "
            "already provides the same translation '%s'",
            "home-assistant-redundant-translation-key",
            "Used when an entity sets a translation_key that resolves to "
            "the same name the device_class already provides. Remove the "
            "translation_key to use the device class translation directly.",
        ),
    }
    options = ()

    _is_platform: bool
    _platform: str | None
    _translations: dict | None
    _components_dir: Path | None
    _module_node: nodes.Module | None

    def visit_module(self, node: nodes.Module) -> None:
        """Load translations for platform modules."""
        self._is_platform = False
        self._platform = None
        self._translations = None
        self._components_dir = None
        self._module_node = None

        if not is_integration_module(node.name):
            return

        parsed = parse_module(node.name)
        if parsed is None or parsed.module is None:
            return

        if parsed.module not in _PLATFORMS_WITH_DEVICE_CLASS_TRANSLATIONS:
            return

        self._is_platform = True
        self._platform = parsed.module
        self._module_node = node
        self._translations = load_translations(node)
        integration_dir = get_integration_dir(node)
        if integration_dir is not None:
            self._components_dir = integration_dir.parent

    def visit_call(self, node: nodes.Call) -> None:
        """Check EntityDescription calls for redundant translation_key."""
        if not self._is_platform or self._translations is None:
            return

        if not node.keywords:
            return

        if (
            isinstance(node.func, nodes.Attribute)
            and "Description" not in node.func.attrname
        ):
            return

        translation_key: str | None = None
        device_class: str | None = None
        tk_keyword: nodes.Keyword | None = None

        for kw in node.keywords:
            if kw.arg == "translation_key":
                translation_key = _resolve_const_string(kw.value)
                tk_keyword = kw
            elif kw.arg == "device_class":
                device_class = _resolve_device_class_value(kw.value)

        if translation_key is None or device_class is None or tk_keyword is None:
            return

        if _resolve_description_class(node) is None:
            return

        self._check_redundant(node, tk_keyword, translation_key, device_class)

    def _check_redundant(
        self,
        node: nodes.Call,
        tk_keyword: nodes.Keyword,
        translation_key: str,
        device_class: str,
    ) -> None:
        """Compare entity translation against device class translation."""
        assert self._platform is not None
        assert self._translations is not None

        entity_trans = (
            self._translations.get("entity", {})
            .get(self._platform, {})
            .get(translation_key, {})
        )
        if not isinstance(entity_trans, dict):
            return

        entity_name = entity_trans.get("name")
        if not isinstance(entity_name, str):
            return

        entity_name = resolve_translation_reference(entity_name, self._components_dir)

        assert self._module_node is not None
        dc_translations = _load_device_class_translations(
            self._module_node, self._platform
        )
        dc_name = dc_translations.get(device_class)
        if dc_name is None:
            return

        dc_name = resolve_translation_reference(dc_name, self._components_dir)

        if entity_name == dc_name:
            self.add_message(
                "home-assistant-redundant-translation-key",
                node=tk_keyword,
                args=(translation_key, device_class, entity_name),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantTranslationKeyChecker(linter))
