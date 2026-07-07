"""Tests for the config flow translations checker."""

import json
from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.flow_translations import (
    ConfigFlowTranslationsChecker,
)
from pylint_home_assistant.helpers.translations import clear_translations_cache
import pytest

from . import assert_no_messages


@pytest.fixture(name="flow_translations_checker")
def flow_translations_checker_fixture(
    linter: UnittestLinter,
) -> ConfigFlowTranslationsChecker:
    """Fixture to provide a config flow translations checker."""
    clear_translations_cache()
    return ConfigFlowTranslationsChecker(linter)


def _make_integration(tmp_path: Path, strings: dict | None = None) -> Path:
    """Create a fake integration with optional strings.json."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if strings is not None:
        (integration_dir / "strings.json").write_text(json.dumps(strings))
    return integration_dir


# --- Config flow tests ---


def test_config_flow_translated_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when all config flow fields have translations."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host", "port": "Port"}}}}},
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Optional("port"): int,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_config_flow_missing_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning when a config flow field is missing a translation."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host"}}}}},
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("missing_field"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-config-flow-field-not-translated"
    assert "missing_field" in messages[0].args[0]


# --- Options flow tests ---


def test_options_flow_translated_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when options flow fields have translations."""
    integration_dir = _make_integration(
        tmp_path,
        {"options": {"step": {"init": {"data": {"interval": "Update interval"}}}}},
    )

    root_node = astroid.parse(
        """
class MyOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("interval"): int,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_options_flow_missing_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning when an options flow field is missing a translation."""
    integration_dir = _make_integration(
        tmp_path,
        {"options": {"step": {"init": {"data": {"interval": "Update interval"}}}}},
    )

    root_node = astroid.parse(
        """
class MyOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("interval"): int,
                vol.Required("missing"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-options-flow-field-not-translated"


# --- Subentry flow tests ---


def test_subentry_flow_translated_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when subentry flow fields have translations."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config_subentries": {
                "my_sub": {
                    "step": {"user": {"data": {"name": "Name"}}},
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    @classmethod
    def async_get_supported_subentry_types(cls, config_entry):
        return {"my_sub": MySubentryFlow}

class MySubentryFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_subentry_flow_missing_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning when a subentry flow field is missing a translation."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config_subentries": {
                "my_sub": {
                    "step": {"user": {"data": {"name": "Name"}}},
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    @classmethod
    def async_get_supported_subentry_types(cls, config_entry):
        return {"my_sub": MySubentryFlow}

class MySubentryFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("missing"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-subentry-flow-field-not-translated"


def test_subentry_shared_handler_missing_in_one_type(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning when field is missing in one of the mapped subentry types."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config_subentries": {
                "type_a": {
                    "step": {"user": {"data": {"name": "Name"}}},
                },
                "type_b": {
                    "step": {"user": {"data": {}}},
                },
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    @classmethod
    def async_get_supported_subentry_types(cls, config_entry):
        return {"type_a": SharedFlow, "type_b": SharedFlow}

class SharedFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-subentry-flow-field-not-translated"
    assert "type_b" in messages[0].args[2]


def test_subentry_section_field_missing(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning when a subentry flow section field is missing a translation."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config_subentries": {
                "my_sub": {
                    "step": {
                        "user": {
                            "sections": {"advanced": {"data": {"timeout": "Timeout"}}}
                        }
                    },
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    @classmethod
    def async_get_supported_subentry_types(cls, config_entry):
        return {"my_sub": MySubentryFlow}

class MySubentryFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("advanced"): section(
                    vol.Schema({
                        vol.Required("timeout"): int,
                        vol.Required("retries"): int,
                    }),
                ),
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-subentry-flow-field-not-translated"
    assert "retries" in messages[0].args[0]


# --- Schema extend tests ---


def test_schema_extend_base_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Warning for untranslated base schema field when using schema.extend()."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"port": "Port"}}}}},
    )

    root_node = astroid.parse(
        """
BASE_SCHEMA = vol.Schema({vol.Required("host"): str})

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=BASE_SCHEMA.extend({vol.Optional("port"): int}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-config-flow-field-not-translated"
    assert "host" in messages[0].args[0]


def test_schema_extend_all_translated_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when all fields (base + extension) are translated."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host", "port": "Port"}}}}},
    )

    root_node = astroid.parse(
        """
BASE_SCHEMA = vol.Schema({vol.Required("host"): str})

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=BASE_SCHEMA.extend({vol.Optional("port"): int}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


# --- Inference tests ---


def test_implicit_step_id_from_method(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that step_id is inferred from async_step_* method name."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host"}}}}},
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            data_schema=vol.Schema({vol.Required("host"): str}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_implicit_step_id_missing_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that missing field is flagged when step_id is inferred."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host"}}}}},
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("missing"): str,
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-config-flow-field-not-translated"
    assert "missing" in messages[0].args[0]


def test_section_fields_translated_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that section fields are checked against sections translations."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config": {
                "step": {
                    "user": {
                        "data": {"host": "Host"},
                        "sections": {
                            "advanced": {
                                "data": {"ssl": "Use SSL", "verify": "Verify"},
                            }
                        },
                    }
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("advanced"): section(
                    vol.Schema({
                        vol.Required("ssl"): bool,
                        vol.Required("verify"): bool,
                    }),
                    {"collapsed": True},
                ),
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_section_missing_field_flagged(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that missing section fields are flagged."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config": {
                "step": {
                    "user": {
                        "data": {"host": "Host"},
                        "sections": {
                            "advanced": {
                                "data": {"ssl": "Use SSL"},
                            }
                        },
                    }
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("advanced"): section(
                    vol.Schema({
                        vol.Required("ssl"): bool,
                        vol.Required("missing_field"): bool,
                    }),
                    {"collapsed": True},
                ),
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert "missing_field" in messages[0].args[0]


def test_section_attribute_form_ok(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that data_entry_flow.section(...) is recognized as a section."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "config": {
                "step": {
                    "user": {
                        "data": {"host": "Host"},
                        "sections": {
                            "advanced": {
                                "data": {"ssl": "Use SSL"},
                            }
                        },
                    }
                }
            }
        },
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("advanced"): data_entry_flow.section(
                    vol.Schema({vol.Required("ssl"): bool}),
                    {"collapsed": True},
                ),
            }),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_constant_field_names_resolved(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that constant field names are resolved via inference."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host"}}}}},
    )

    root_node = astroid.parse(
        """
CONF_HOST = "host"

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_dict_unpacking_in_schema(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that **dict unpacking in schema dicts is resolved."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host", "port": "Port"}}}}},
    )

    root_node = astroid.parse(
        """
BASE = {vol.Required("host"): str}

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({**BASE, vol.Optional("port"): int}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_schema_variable_resolved(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that schema passed via a variable is resolved."""
    integration_dir = _make_integration(
        tmp_path,
        {"config": {"step": {"user": {"data": {"host": "Host"}}}}},
    )

    root_node = astroid.parse(
        """
USER_SCHEMA = vol.Schema({vol.Required("host"): str})

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


# --- Edge cases ---


def test_no_strings_json_no_warning(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when strings.json doesn't exist."""
    integration_dir = _make_integration(tmp_path)

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str}),
        )
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_not_config_flow_module_ignored(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Non-config_flow modules are ignored."""
    integration_dir = _make_integration(
        tmp_path, {"config": {"step": {"user": {"data": {}}}}}
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str}),
        )
""",
        "homeassistant.components.test_int.sensor",
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_no_data_schema_no_warning(
    linter: UnittestLinter,
    flow_translations_checker: ConfigFlowTranslationsChecker,
    tmp_path: Path,
) -> None:
    """No warning when async_show_form has no data_schema."""
    integration_dir = _make_integration(
        tmp_path, {"config": {"step": {"link": {"title": "Link"}}}}
    )

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_link(self, user_input=None):
        return self.async_show_form(step_id="link")
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(flow_translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
