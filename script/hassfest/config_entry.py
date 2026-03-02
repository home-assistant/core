"""Validate config entry schemas."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import CONF_SELECTOR
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration

VERSION_SCHEMA = vol.Schema(
    {
        vol.Required("major"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("minor"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)

FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional("required"): bool,
        vol.Optional("default"): object,
        vol.Optional("example"): object,
        vol.Required(CONF_SELECTOR): selector.validate_selector,
    }
)

FIELDS_SCHEMA = vol.Schema({str: FIELD_SCHEMA})

SECTION_SCHEMA = vol.Schema({vol.Required("fields"): FIELDS_SCHEMA})

VERSIONED_SCHEMA = vol.Schema(
    {
        vol.Required("version"): VERSION_SCHEMA,
        vol.Required("data"): SECTION_SCHEMA,
        vol.Required("options"): SECTION_SCHEMA,
    }
)

SUBENTRY_SCHEMA = vol.Schema({vol.Required("versions"): [VERSIONED_SCHEMA]})

CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("versions"): [VERSIONED_SCHEMA],
        vol.Optional("subentries", default={}): {str: SUBENTRY_SCHEMA},
    }
)

ROOT_SCHEMA = vol.Schema({vol.Required("config_entry"): CONFIG_ENTRY_SCHEMA})


def _dotted_name(node: ast.expr) -> str | None:
    """Return dotted name for Name/Attribute nodes."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if base := _dotted_name(node.value):
            return f"{base}.{node.attr}"
    return None


def _parse_module(path: Path) -> ast.Module | None:
    """Parse a python module from path."""
    if not path.is_file():
        return None

    try:
        return ast.parse(path.read_text())
    except SyntaxError, OSError:
        return None


def _string_constant_assignments(module: ast.Module) -> dict[str, str]:
    """Extract top-level string constant assignments."""
    constants: dict[str, str] = {}
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.targets[0].id] = node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.target.id] = node.value.value
    return constants


def _resolve_field_name(node: ast.expr, constants: dict[str, str]) -> str | None:
    """Resolve a config field name from an AST expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in constants:
            return constants[node.id]
        if node.id.startswith("CONF_"):
            return node.id[5:].lower()
    if isinstance(node, ast.Attribute):
        if dotted := _dotted_name(node):
            return constants.get(dotted)
    return None


def _extract_dict_field_names(
    dict_node: ast.Dict, constants: dict[str, str]
) -> set[str]:
    """Extract field names from a dict literal used as entry data/options."""
    fields: set[str] = set()
    for key in dict_node.keys:
        if key is None:
            continue
        if resolved := _resolve_field_name(key, constants):
            fields.add(resolved)
    return fields


def _walk_nested_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
    """Return flattened nested statements."""
    flattened: list[ast.stmt] = []
    queue = list(statements)
    while queue:
        statement = queue.pop(0)
        flattened.append(statement)
        nested: list[list[ast.stmt]] = []
        if isinstance(statement, ast.If):
            nested += [statement.body, statement.orelse]
        elif isinstance(statement, ast.Try):
            nested += [statement.body, statement.orelse, statement.finalbody]
            nested += [handler.body for handler in statement.handlers]
        elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            nested += [statement.body, statement.orelse]
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            nested += [statement.body]
        elif isinstance(statement, ast.Match):
            nested += [case.body for case in statement.cases]
        for children in nested:
            queue.extend(children)
    return flattened


def _create_entry_data_literal_keys(module: ast.Module) -> set[str]:
    """Extract literal create-entry data keys from config_flow.py."""
    constants = _string_constant_assignments(module)
    keys: set[str] = set()

    def collect_from_function(
        function_node: ast.AsyncFunctionDef | ast.FunctionDef,
    ) -> None:
        local_dicts: dict[str, set[str]] = {}
        for statement in _walk_nested_statements(function_node.body):
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and isinstance(statement.value, ast.Dict)
            ):
                local_dicts[statement.targets[0].id] = _extract_dict_field_names(
                    statement.value, constants
                )
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and isinstance(statement.value, ast.Dict)
            ):
                local_dicts[statement.target.id] = _extract_dict_field_names(
                    statement.value, constants
                )

            call_node: ast.Call | None = None
            if isinstance(statement, (ast.Expr, ast.Return)) and isinstance(
                statement.value, ast.Call
            ):
                call_node = statement.value
            if call_node is None:
                continue

            call_name = _dotted_name(call_node.func)
            if not call_name or not call_name.endswith("async_create_entry"):
                continue

            for keyword in call_node.keywords:
                if keyword.arg != "data":
                    continue
                if isinstance(keyword.value, ast.Dict):
                    keys.update(_extract_dict_field_names(keyword.value, constants))
                elif isinstance(keyword.value, ast.Name):
                    keys.update(local_dicts.get(keyword.value.id, set()))

    for node in module.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            collect_from_function(node)
        elif isinstance(node, ast.ClassDef):
            base_names = {_dotted_name(base) for base in node.bases}
            if any(
                base_name and base_name.endswith("OptionsFlow")
                for base_name in base_names
            ):
                continue
            for child in node.body:
                if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    collect_from_function(child)

    return keys


def _uses_register_webhook_flow(module: ast.Module) -> bool:
    """Return if config flow uses register_webhook_flow helper."""
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = _dotted_name(node.func)
        if call_name and call_name.endswith("register_webhook_flow"):
            return True
    return False


def _uses_abstract_oauth2_flow_handler(module: ast.Module) -> bool:
    """Return if config flow uses AbstractOAuth2FlowHandler."""
    for node in ast.walk(module):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = _dotted_name(base)
            if base_name and base_name.endswith("AbstractOAuth2FlowHandler"):
                return True
    return False


def _collect_schema_import_aliases(module: ast.Module) -> tuple[set[str], set[str]]:
    """Collect aliases used for schema config flow imports."""
    schema_handler_names = {"SchemaConfigFlowHandler"}
    schema_module_aliases = {"homeassistant.helpers.schema_config_entry_flow"}

    for node in module.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "homeassistant.helpers.schema_config_entry_flow":
                for alias in node.names:
                    if alias.name == "SchemaConfigFlowHandler":
                        schema_handler_names.add(alias.asname or alias.name)
            elif node.module == "homeassistant.helpers":
                for alias in node.names:
                    if alias.name == "schema_config_entry_flow":
                        schema_module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "homeassistant.helpers.schema_config_entry_flow":
                    schema_module_aliases.add(alias.asname or alias.name.split(".")[-1])

    return schema_handler_names, schema_module_aliases


def _uses_schema_config_flow_handler_base(
    dotted_base: str, schema_handler_names: set[str], schema_module_aliases: set[str]
) -> bool:
    """Return if a class base points to SchemaConfigFlowHandler."""
    if dotted_base in schema_handler_names:
        return True
    if dotted_base.endswith(".SchemaConfigFlowHandler"):
        module_name = dotted_base.rsplit(".", 1)[0]
        return module_name in schema_module_aliases
    return False


def _collect_class_metadata(
    module: ast.Module,
    schema_handler_names: set[str],
    schema_module_aliases: set[str],
) -> tuple[dict[str, set[str]], dict[str, bool], dict[str, bool], dict[str, bool]]:
    """Collect class metadata needed to detect schema config flow behavior."""
    class_local_bases: dict[str, set[str]] = {}
    class_is_schema: dict[str, bool] = {}
    class_has_domain_kw: dict[str, bool] = {}
    class_has_create_entry_override: dict[str, bool] = {}

    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue

        direct_schema_base = False
        local_bases: set[str] = set()
        for base in node.bases:
            dotted_base = _dotted_name(base)
            if dotted_base is None:
                continue
            if _uses_schema_config_flow_handler_base(
                dotted_base, schema_handler_names, schema_module_aliases
            ):
                direct_schema_base = True
                continue
            if "." not in dotted_base:
                local_bases.add(dotted_base)

        class_local_bases[node.name] = local_bases
        class_is_schema[node.name] = direct_schema_base
        class_has_domain_kw[node.name] = any(
            keyword.arg == "domain" for keyword in node.keywords
        )
        class_has_create_entry_override[node.name] = any(
            isinstance(body_node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and body_node.name == "async_create_entry"
            for body_node in node.body
        )

    return (
        class_local_bases,
        class_is_schema,
        class_has_domain_kw,
        class_has_create_entry_override,
    )


def _expand_schema_inheritance(
    class_local_bases: dict[str, set[str]], class_is_schema: dict[str, bool]
) -> None:
    """Expand schema inheritance to local child classes."""
    changed = True
    while changed:
        changed = False
        for class_name, local_bases in class_local_bases.items():
            if class_is_schema[class_name]:
                continue
            if any(class_is_schema.get(base, False) for base in local_bases):
                class_is_schema[class_name] = True
                changed = True


def _class_or_parent_overrides_create_entry(
    class_name: str,
    class_local_bases: dict[str, set[str]],
    class_is_schema: dict[str, bool],
    class_has_create_entry_override: dict[str, bool],
    seen: set[str] | None = None,
) -> bool:
    """Return if class or local schema ancestor overrides create entry."""
    if seen is None:
        seen = set()
    if class_name in seen:
        return False
    seen.add(class_name)

    if class_has_create_entry_override.get(class_name, False):
        return True
    for base in class_local_bases.get(class_name, set()):
        if class_is_schema.get(base, False) and _class_or_parent_overrides_create_entry(
            base,
            class_local_bases,
            class_is_schema,
            class_has_create_entry_override,
            seen,
        ):
            return True
    return False


def _schema_config_flow_stores_in_options_only(config_flow_path: Path) -> bool:
    """Return if schema config flow stores entry values in options."""
    if (module := _parse_module(config_flow_path)) is None:
        return False

    schema_handler_names, schema_module_aliases = _collect_schema_import_aliases(module)
    (
        class_local_bases,
        class_is_schema,
        class_has_domain_kw,
        class_has_create_entry_override,
    ) = _collect_class_metadata(module, schema_handler_names, schema_module_aliases)

    if not class_is_schema:
        return False

    _expand_schema_inheritance(class_local_bases, class_is_schema)

    domain_schema_classes = [
        class_name
        for class_name, is_schema in class_is_schema.items()
        if is_schema and class_has_domain_kw[class_name]
    ]
    if not domain_schema_classes:
        return False

    return all(
        not _class_or_parent_overrides_create_entry(
            class_name,
            class_local_bases,
            class_is_schema,
            class_has_create_entry_override,
        )
        for class_name in domain_schema_classes
    )


def _class_flow_kind(class_node: ast.ClassDef) -> str | None:
    """Return class flow kind."""
    bases = {_dotted_name(base) for base in class_node.bases}
    if any(base and base.endswith("OptionsFlow") for base in bases):
        return "options"
    if any(base and "ConfigFlow" in base for base in bases):
        return "config"
    return None


def _collect_schema_definitions(module: ast.Module) -> dict[str, ast.expr]:
    """Collect top-level schema expression definitions."""
    schema_defs: dict[str, ast.expr] = {}
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            schema_defs[node.targets[0].id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            schema_defs[node.target.id] = node.value
    return schema_defs


def _extract_schema_keys(
    expression: ast.expr,
    constants: dict[str, str],
    schema_defs: dict[str, ast.expr],
    seen: set[str] | None = None,
) -> set[str]:
    """Extract field keys from a voluptuous schema expression."""
    if seen is None:
        seen = set()

    if isinstance(expression, ast.Name):
        if expression.id in seen:
            return set()
        seen.add(expression.id)
        if expression.id in schema_defs:
            return _extract_schema_keys(
                schema_defs[expression.id], constants, schema_defs, seen
            )
        return set()

    if isinstance(expression, ast.Call):
        call_name = _dotted_name(expression.func)
        if (
            call_name
            and call_name.endswith("Schema")
            and expression.args
            and isinstance(expression.args[0], ast.Dict)
        ):
            keys: set[str] = set()
            for key_expr in expression.args[0].keys:
                if key_expr is None:
                    continue
                if key := _resolve_field_name(key_expr, constants):
                    keys.add(key)
            return keys

        if (
            call_name
            and call_name.endswith("add_suggested_values_to_schema")
            and expression.args
        ):
            return _extract_schema_keys(
                expression.args[0], constants, schema_defs, seen
            )

    return set()


def _user_input_schema_storage_fields(module: ast.Module) -> tuple[set[str], set[str]]:
    """Extract fields persisted via async_create_entry(data=user_input)."""
    constants = _string_constant_assignments(module)
    schema_defs = _collect_schema_definitions(module)
    data_fields: set[str] = set()
    options_fields: set[str] = set()

    for class_node in [node for node in module.body if isinstance(node, ast.ClassDef)]:
        if (flow_kind := _class_flow_kind(class_node)) is None:
            continue

        step_schemas: dict[str, set[str]] = {}

        for function_node in [
            node
            for node in class_node.body
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name.startswith("async_step_")
        ]:
            step_name = function_node.name.removeprefix("async_step_")
            schema_keys: set[str] = set()

            for call_node in [
                node for node in ast.walk(function_node) if isinstance(node, ast.Call)
            ]:
                call_name = _dotted_name(call_node.func)
                if not call_name or not call_name.endswith("async_show_form"):
                    continue
                for keyword in call_node.keywords:
                    if keyword.arg != "data_schema":
                        continue
                    schema_keys.update(
                        _extract_schema_keys(keyword.value, constants, schema_defs)
                    )

            if schema_keys:
                step_schemas[step_name] = schema_keys

        for function_node in [
            node
            for node in class_node.body
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name.startswith("async_step_")
        ]:
            step_name = function_node.name.removeprefix("async_step_")
            schema_keys = step_schemas.get(step_name, set())
            if not schema_keys:
                continue

            for call_node in [
                node for node in ast.walk(function_node) if isinstance(node, ast.Call)
            ]:
                call_name = _dotted_name(call_node.func)
                if not call_name or not call_name.endswith("async_create_entry"):
                    continue

                for keyword in call_node.keywords:
                    if (
                        keyword.arg == "data"
                        and isinstance(keyword.value, ast.Name)
                        and keyword.value.id == "user_input"
                    ):
                        if flow_kind == "config":
                            data_fields.update(schema_keys)
                        else:
                            options_fields.update(schema_keys)

    return data_fields, options_fields


def _validate_unique_versions(
    integration: Integration,
    location: str,
    versions: list[dict[str, Any]],
) -> None:
    """Validate that versions are unique within a block."""
    seen: set[tuple[int, int]] = set()
    for version_config in versions:
        version = version_config["version"]
        version_key = (version["major"], version["minor"])
        if version_key in seen:
            integration.add_error(
                "config_entry",
                (
                    f"Duplicate version {version_key[0]}.{version_key[1]} "
                    f"found in {location}"
                ),
            )
            continue
        seen.add(version_key)


def _validate_integration(config: Config, integration: Integration) -> None:
    """Validate config.yaml for an integration."""
    config_yaml_path = integration.path / "config.yaml"

    if not config_yaml_path.is_file():
        if integration.config_flow:
            integration.add_error(
                "config_entry",
                "Integrations with a config flow must define config.yaml",
            )
        return

    try:
        data = load_yaml_dict(str(config_yaml_path))
    except HomeAssistantError:
        integration.add_error("config_entry", "Invalid config.yaml")
        return

    try:
        validated = ROOT_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "config_entry", f"Invalid config.yaml: {humanize_error(data, err)}"
        )
        return

    config_entry = validated["config_entry"]
    _validate_unique_versions(
        integration, "config_entry.versions", config_entry["versions"]
    )

    if _schema_config_flow_stores_in_options_only(integration.path / "config_flow.py"):
        for version_config in config_entry["versions"]:
            version = version_config["version"]
            if version_config["data"]["fields"]:
                integration.add_error(
                    "config_entry",
                    (
                        "Integrations using SchemaConfigFlowHandler without "
                        "async_create_entry override must have empty "
                        f"config_entry.versions data.fields (found in version "
                        f"{version['major']}.{version['minor']})"
                    ),
                )

    config_flow_module = _parse_module(integration.path / "config_flow.py")

    all_data_fields_empty = all(
        not version_config["data"]["fields"]
        for version_config in config_entry["versions"]
    )

    if (
        all_data_fields_empty
        and config_flow_module
        and _uses_register_webhook_flow(config_flow_module)
    ):
        required_fields = {"webhook_id", "cloudhook"}
        for version_config in config_entry["versions"]:
            version = version_config["version"]
            data_fields = set(version_config["data"]["fields"])
            if missing_fields := sorted(required_fields - data_fields):
                integration.add_error(
                    "config_entry",
                    (
                        "Webhook helper flows must define webhook_id/cloudhook in "
                        "config_entry.versions data.fields "
                        f"(missing {', '.join(missing_fields)} in version "
                        f"{version['major']}.{version['minor']})"
                    ),
                )

    if (
        all_data_fields_empty
        and config_flow_module
        and _uses_abstract_oauth2_flow_handler(config_flow_module)
    ):
        required_fields = {"auth_implementation", "token"}
        for version_config in config_entry["versions"]:
            version = version_config["version"]
            data_fields = set(version_config["data"]["fields"])
            if missing_fields := sorted(required_fields - data_fields):
                integration.add_error(
                    "config_entry",
                    (
                        "OAuth2 helper flows must define auth_implementation/token in "
                        "config_entry.versions data.fields "
                        f"(missing {', '.join(missing_fields)} in version "
                        f"{version['major']}.{version['minor']})"
                    ),
                )

    if all_data_fields_empty and config_flow_module:
        literal_data_keys = _create_entry_data_literal_keys(config_flow_module)
        if literal_data_keys:
            for version_config in config_entry["versions"]:
                version = version_config["version"]
                data_fields = set(version_config["data"]["fields"])
                if missing_fields := sorted(literal_data_keys - data_fields):
                    integration.add_error(
                        "config_entry",
                        (
                            "config_entry.versions data.fields is missing keys used in "
                            "async_create_entry(data=...) "
                            f"(missing {', '.join(missing_fields)} in version "
                            f"{version['major']}.{version['minor']})"
                        ),
                    )

    if config_flow_module:
        expected_data_fields, expected_options_fields = (
            _user_input_schema_storage_fields(config_flow_module)
        )
        current_version_config = max(
            config_entry["versions"],
            key=lambda version_config: (
                version_config["version"]["major"],
                version_config["version"]["minor"],
            ),
        )
        current_version = current_version_config["version"]

        if expected_data_fields:
            actual_data_fields = set(current_version_config["data"]["fields"])
            if missing_fields := sorted(expected_data_fields - actual_data_fields):
                integration.add_error(
                    "config_entry",
                    (
                        "config_entry current version data.fields is missing keys "
                        "from steps that store user_input via async_create_entry "
                        f"(missing {', '.join(missing_fields)} in version "
                        f"{current_version['major']}.{current_version['minor']})"
                    ),
                )

        if expected_options_fields:
            actual_options_fields = set(current_version_config["options"]["fields"])
            if missing_fields := sorted(
                expected_options_fields - actual_options_fields
            ):
                integration.add_error(
                    "config_entry",
                    (
                        "config_entry current version options.fields is missing keys "
                        "from options steps that store user_input via "
                        f"async_create_entry (missing {', '.join(missing_fields)} in "
                        f"version {current_version['major']}.{current_version['minor']})"
                    ),
                )

    for subentry_type, subentry_config in config_entry.get("subentries", {}).items():
        _validate_unique_versions(
            integration,
            f"config_entry.subentries.{subentry_type}.versions",
            subentry_config["versions"],
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate config entry schemas."""
    for integration in integrations.values():
        _validate_integration(config, integration)
