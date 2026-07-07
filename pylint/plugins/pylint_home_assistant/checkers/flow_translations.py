"""Checker for missing config/options/subentry flow form translations.

When a flow calls ``async_show_form`` with a ``data_schema``, every
field in the schema needs a corresponding translation entry in
``strings.json``.

The expected translation paths are::

    config.step.{step_id}.data.{field_name}
    config.step.{step_id}.sections.{section_key}.data.{field_name}
    options.step.{step_id}.data.{field_name}
    options.step.{step_id}.sections.{section_key}.data.{field_name}
    config_subentries.{subentry_type}.step.{step_id}.data.{field_name}
    config_subentries.{subentry_type}.step.{step_id}.sections.{section_key}.data.{field_name}

- ``W7425``: Missing config flow field translation
- ``W7427``: Missing options flow field translation
- ``W7430``: Missing subentry flow field translation
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.translations import load_translations

_InferenceError = astroid.exceptions.InferenceError


def _extract_step_id(call: nodes.Call) -> str | None:
    """Extract step_id from an async_show_form call.

    Falls back to the enclosing method name if step_id is omitted
    (e.g., ``async_step_user`` -> ``"user"``).
    """
    for kw in call.keywords:
        if kw.arg == "step_id":
            match kw.value:
                case nodes.Const(value=str() as value):
                    return value
            try:
                for inferred in kw.value.infer():
                    match inferred:
                        case nodes.Const(value=str() as value):
                            return value
            except _InferenceError:
                pass
            return None

    # No step_id keyword: infer from enclosing async_step_* method
    current = call.parent
    while current is not None:
        if isinstance(current, nodes.FunctionDef):
            if current.name.startswith("async_step_"):
                return str(current.name).removeprefix("async_step_")
            break
        current = current.parent
    return None


# Result types for schema extraction


class _Field:
    """A regular form field."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class _Section:
    """A section containing nested fields."""

    __slots__ = ("fields", "key")

    def __init__(self, key: str, fields: list[str]) -> None:
        self.key = key
        self.fields = fields


def _extract_schema_items(call: nodes.Call) -> list[_Field | _Section]:
    """Extract fields and sections from the data_schema keyword argument."""
    schema_node = None
    for kw in call.keywords:
        if kw.arg == "data_schema":
            schema_node = kw.value
            break

    if schema_node is None:
        return []

    return _extract_items_from_node(schema_node)


def _extract_items_from_node(
    node: nodes.NodeNG,
) -> list[_Field | _Section]:
    """Recursively extract fields and sections from a schema node."""
    items: list[_Field | _Section] = []

    # schema.extend({...}) - extract fields from both base and extension
    if isinstance(node, nodes.Call) and node.args:
        match node.func:
            case nodes.Attribute(attrname="extend"):
                items.extend(_extract_items_from_node(node.func.expr))
                items.extend(_extract_items_from_node(node.args[0]))
                return items
        return _extract_items_from_node(node.args[0])

    # Direct dict literal
    if isinstance(node, nodes.Dict):
        for key, value in node.items:
            if isinstance(key, nodes.DictUnpack):
                try:
                    for inferred in value.infer():
                        if isinstance(inferred, nodes.Dict):
                            items.extend(_extract_items_from_node(inferred))
                except _InferenceError:
                    pass
                continue

            name = _resolve_field_name(key)
            if name is None:
                continue

            # Check if the value is a section(...) call
            section_fields = _extract_section_fields(value)
            if section_fields is not None:
                items.append(_Section(name, section_fields))
            else:
                items.append(_Field(name))
        return items

    # Variable reference: resolve via AST assignment lookup
    if isinstance(node, nodes.Name):
        try:
            _, assigns = node.lookup(node.name)
            for assign in assigns:
                if isinstance(assign, nodes.AssignName) and isinstance(
                    assign.parent, nodes.Assign
                ):
                    result = _extract_items_from_node(assign.parent.value)
                    if result:
                        return result
        except astroid.exceptions.NameInferenceError:
            pass

    # Fallback: try type inference
    try:
        for inferred in node.infer():
            if isinstance(inferred, (nodes.Call, nodes.Dict)):
                return _extract_items_from_node(inferred)
    except _InferenceError:
        pass

    return items


def _extract_section_fields(node: nodes.NodeNG) -> list[str] | None:
    """Extract field names from a section(...) call.

    Returns a list of field names if the node is a section() call,
    or None if it's not a section.
    """
    if not isinstance(node, nodes.Call):
        return None
    # Match section(...) or data_entry_flow.section(...)
    match node.func:
        case nodes.Name(name="section"):
            pass
        case nodes.Attribute(attrname="section"):
            pass
        case _:
            return None
    if not node.args:
        return None

    # section(vol.Schema({...}), ...) - first arg is the schema
    inner_items = _extract_items_from_node(node.args[0])
    return [item.name for item in inner_items if isinstance(item, _Field)]


def _resolve_field_name(node: nodes.NodeNG) -> str | None:
    """Resolve a schema key to a field name string."""
    if isinstance(node, nodes.Call) and node.args:
        match node.func:
            case nodes.Attribute(attrname="Required" | "Optional"):
                return _resolve_field_name(node.args[0])

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


def _find_enclosing_class(node: nodes.Call) -> nodes.ClassDef | None:
    """Find the enclosing class definition for a call node."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.ClassDef):
            return current
        current = current.parent
    return None


def _get_flow_type(class_node: nodes.ClassDef) -> str | None:
    """Determine flow type from a class definition."""
    for base in class_node.bases:
        match base:
            case nodes.Name(name=name):
                if "SubentryFlow" in name:
                    return "subentry"
                if "OptionsFlow" in name:
                    return "options"
                if "ConfigFlow" in name or "FlowHandler" in name:
                    return "config"
            case nodes.Attribute(attrname=name):
                if "SubentryFlow" in name:
                    return "subentry"
                if "OptionsFlow" in name:
                    return "options"
                if "ConfigFlow" in name or "FlowHandler" in name:
                    return "config"

    try:
        for ancestor in class_node.ancestors():
            if "SubentryFlow" in ancestor.name:
                return "subentry"
            if "OptionsFlow" in ancestor.name:
                return "options"
            if "ConfigFlow" in ancestor.name:
                return "config"
    except _InferenceError:
        pass

    return None


def _resolve_subentry_types(module: nodes.Module, handler_class_name: str) -> list[str]:
    """Resolve subentry type names for a handler class."""
    subentry_types: list[str] = []

    for node in module.body:
        if not isinstance(node, nodes.ClassDef):
            continue
        if _get_flow_type(node) != "config":
            continue

        for method in node.mymethods():
            if method.name != "async_get_supported_subentry_types":
                continue
            for child in method.body:
                if not isinstance(child, nodes.Return):
                    continue
                if not isinstance(child.value, nodes.Dict):
                    continue
                for key, value in child.value.items:
                    if isinstance(key, nodes.DictUnpack):
                        continue
                    key_str = _resolve_field_name(key)
                    if key_str and isinstance(value, nodes.Name):
                        if value.name == handler_class_name:
                            subentry_types.append(key_str)

    return subentry_types


class ConfigFlowTranslationsChecker(BaseChecker):
    """Checker for missing flow form translations."""

    name = "home_assistant_config_flow_translations"
    priority = -1
    msgs = {
        "W7425": (
            "Form field '%s' in step '%s' is missing a translation in "
            "strings.json (expected at %s)",
            "home-assistant-config-flow-field-not-translated",
            "Used when a config flow form field does not have a "
            "corresponding translation in strings.json.",
        ),
        "W7427": (
            "Form field '%s' in step '%s' is missing a translation in "
            "strings.json (expected at %s)",
            "home-assistant-options-flow-field-not-translated",
            "Used when an options flow form field does not have a "
            "corresponding translation in strings.json.",
        ),
        "W7430": (
            "Form field '%s' in step '%s' is missing a translation in "
            "strings.json (expected at %s)",
            "home-assistant-subentry-flow-field-not-translated",
            "Used when a subentry flow form field does not have a "
            "corresponding translation in strings.json.",
        ),
    }
    options = ()

    _translations: dict | None
    _is_config_flow: bool
    _module_node: nodes.Module | None

    def visit_module(self, node: nodes.Module) -> None:
        """Load translations for config_flow modules."""
        platform = get_module_platform(node.name)
        self._is_config_flow = platform == "config_flow"
        self._translations = None
        self._module_node = None
        if self._is_config_flow:
            self._translations = load_translations(node)
            self._module_node = node

    def visit_call(self, node: nodes.Call) -> None:
        """Check async_show_form calls for translated fields."""
        if not self._is_config_flow or self._translations is None:
            return

        if not isinstance(node.func, nodes.Attribute):
            return
        if node.func.attrname != "async_show_form":
            return

        step_id = _extract_step_id(node)
        if step_id is None:
            return

        schema_items = _extract_schema_items(node)
        if not schema_items:
            return

        class_node = _find_enclosing_class(node)
        if class_node is None:
            return

        flow_type = _get_flow_type(class_node) or "config"

        if flow_type == "config":
            self._check_flow(
                node,
                step_id,
                schema_items,
                "config",
                "home-assistant-config-flow-field-not-translated",
            )
        elif flow_type == "options":
            self._check_flow(
                node,
                step_id,
                schema_items,
                "options",
                "home-assistant-options-flow-field-not-translated",
            )
        elif flow_type == "subentry":
            self._check_subentry_flow(node, step_id, schema_items, class_node)

    def _check_flow(
        self,
        node: nodes.Call,
        step_id: str,
        schema_items: list[_Field | _Section],
        flow_key: str,
        msg_id: str,
    ) -> None:
        """Check fields against translations for config/options flows."""
        assert self._translations is not None
        step_trans = (
            self._translations.get(flow_key, {}).get("step", {}).get(step_id, {})
        )
        data_trans = step_trans.get("data", {})
        sections_trans = step_trans.get("sections", {})

        for item in schema_items:
            if isinstance(item, _Field):
                if item.name not in data_trans:
                    path = f"{flow_key}.step.{step_id}.data.{item.name}"
                    self.add_message(
                        msg_id,
                        node=node,
                        args=(item.name, step_id, path),
                    )
            elif isinstance(item, _Section):
                section_data = sections_trans.get(item.key, {}).get("data", {})
                for field in item.fields:
                    if field not in section_data:
                        path = f"{flow_key}.step.{step_id}.sections.{item.key}.data.{field}"
                        self.add_message(
                            msg_id,
                            node=node,
                            args=(field, step_id, path),
                        )

    def _check_subentry_flow(
        self,
        node: nodes.Call,
        step_id: str,
        schema_items: list[_Field | _Section],
        class_node: nodes.ClassDef,
    ) -> None:
        """Check subentry flow fields against translations."""
        if self._module_node is None:
            return

        subentry_types = _resolve_subentry_types(self._module_node, class_node.name)
        if not subentry_types:
            return

        assert self._translations is not None
        config_subentries = self._translations.get("config_subentries", {})

        for st in subentry_types:
            st_trans = config_subentries.get(st, {})
            step_trans = st_trans.get("step", {}).get(step_id, {})
            for item in schema_items:
                if isinstance(item, _Section):
                    section_data = (
                        step_trans.get("sections", {}).get(item.key, {}).get("data", {})
                    )
                    for field in item.fields:
                        if field not in section_data:
                            path = f"config_subentries.{st}.step.{step_id}.sections.{item.key}.data.{field}"
                            self.add_message(
                                "home-assistant-subentry-flow-field-not-translated",
                                node=node,
                                args=(field, step_id, path),
                            )
                elif isinstance(item, _Field):
                    if item.name not in step_trans.get("data", {}):
                        path = f"config_subentries.{st}.step.{step_id}.data.{item.name}"
                        self.add_message(
                            "home-assistant-subentry-flow-field-not-translated",
                            node=node,
                            args=(item.name, step_id, path),
                        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigFlowTranslationsChecker(linter))
