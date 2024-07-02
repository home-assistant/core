"""Tests for the schema based data entry flows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
    wrapped_entity_config_entry_title,
)
from homeassistant.util.decorator import Registry

from tests.common import MockConfigEntry, MockModule, mock_integration, mock_platform

TEST_DOMAIN = "test"


class MockSchemaConfigFlowHandler(SchemaConfigFlowHandler):
    """Bare minimum SchemaConfigFlowHandler."""

    config_flow = {}

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "title"


@pytest.fixture(name="manager")
def manager_fixture():
    """Return a flow manager."""
    handlers = Registry()
    entries = []

    class FlowManager(data_entry_flow.FlowManager):
        """Test flow manager."""

        async def async_create_flow(self, handler_key, *, context, data):
            """Test create flow."""
            handler = handlers.get(handler_key)

            if handler is None:
                raise data_entry_flow.UnknownHandler

            flow = handler()
            flow.init_step = context.get("init_step", "init")
            return flow

        async def async_finish_flow(self, flow, result):
            """Test finish flow."""
            if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
                result["source"] = flow.context.get("source")
                entries.append(result)
            return result

    mgr = FlowManager(None)
    # pylint: disable-next=attribute-defined-outside-init
    mgr.mock_created_entries = entries
    # pylint: disable-next=attribute-defined-outside-init
    mgr.mock_reg_handler = handlers.register
    return mgr


async def test_name(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test the config flow name is copied from registry entry, with fallback to state."""
    entity_id = "switch.ceiling"

    # No entry or state, use Object ID
    assert wrapped_entity_config_entry_title(hass, entity_id) == "ceiling"

    # State set, use name from state
    hass.states.async_set(entity_id, "on", {"friendly_name": "State Name"})
    assert wrapped_entity_config_entry_title(hass, entity_id) == "State Name"

    # Entity registered, use original name from registry entry
    hass.states.async_remove(entity_id)
    entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        suggested_object_id="ceiling",
        original_name="Original Name",
    )
    hass.states.async_set(entity_id, "on", {"friendly_name": "State Name"})
    assert entry.entity_id == entity_id
    assert wrapped_entity_config_entry_title(hass, entity_id) == "Original Name"
    assert wrapped_entity_config_entry_title(hass, entry.id) == "Original Name"

    # Entity has customized name
    entity_registry.async_update_entity("switch.ceiling", name="Custom Name")
    assert wrapped_entity_config_entry_title(hass, entity_id) == "Custom Name"
    assert wrapped_entity_config_entry_title(hass, entry.id) == "Custom Name"


@pytest.mark.parametrize("marker", [vol.Required, vol.Optional])
async def test_config_flow_advanced_option(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager, marker
) -> None:
    """Test handling of advanced options in config flow."""
    manager.hass = hass

    CONFIG_SCHEMA = vol.Schema(
        {
            marker("option1"): str,
            marker("advanced_no_default", description={"advanced": True}): str,
            marker(
                "advanced_default",
                default="a very reasonable default",
                description={"advanced": True},
            ): str,
        }
    )

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "init": SchemaFlowFormStep(CONFIG_SCHEMA)
    }

    @manager.mock_reg_handler("test")
    class TestFlow(MockSchemaConfigFlowHandler):
        config_flow = CONFIG_FLOW

    # Start flow in basic mode
    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == ["option1"]

    result = await manager.async_configure(result["flow_id"], {"option1": "blabla"})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        "advanced_default": "a very reasonable default",
        "option1": "blabla",
    }
    for option in result["options"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)

    # Start flow in advanced mode
    result = await manager.async_init("test", context={"show_advanced_options": True})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "option1",
        "advanced_no_default",
        "advanced_default",
    ]

    result = await manager.async_configure(
        result["flow_id"], {"advanced_no_default": "abc123", "option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        "advanced_default": "a very reasonable default",
        "advanced_no_default": "abc123",
        "option1": "blabla",
    }
    for option in result["options"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)

    # Start flow in advanced mode
    result = await manager.async_init("test", context={"show_advanced_options": True})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "option1",
        "advanced_no_default",
        "advanced_default",
    ]

    result = await manager.async_configure(
        result["flow_id"],
        {
            "advanced_default": "not default",
            "advanced_no_default": "abc123",
            "option1": "blabla",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {
        "advanced_default": "not default",
        "advanced_no_default": "abc123",
        "option1": "blabla",
    }
    for option in result["options"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)


@pytest.mark.parametrize("marker", [vol.Required, vol.Optional])
async def test_options_flow_advanced_option(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager, marker
) -> None:
    """Test handling of advanced options in options flow."""
    manager.hass = hass

    OPTIONS_SCHEMA = vol.Schema(
        {
            marker("option1"): str,
            marker("advanced_no_default", description={"advanced": True}): str,
            marker(
                "advanced_default",
                default="a very reasonable default",
                description={"advanced": True},
            ): str,
        }
    )

    OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
    }

    class TestFlow(MockSchemaConfigFlowHandler, domain="test"):
        config_flow = {}
        options_flow = OPTIONS_FLOW

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    config_entry = MockConfigEntry(
        data={},
        domain="test",
        options={
            "option1": "blabla",
            "advanced_no_default": "abc123",
            "advanced_default": "not default",
        },
    )
    config_entry.add_to_hass(hass)

    # Start flow in basic mode
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == ["option1"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blublu"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "advanced_default": "not default",
        "advanced_no_default": "abc123",
        "option1": "blublu",
    }
    for option in result["data"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)

    # Start flow in advanced mode
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "option1",
        "advanced_no_default",
        "advanced_default",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"advanced_no_default": "def456", "option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "advanced_default": "a very reasonable default",
        "advanced_no_default": "def456",
        "option1": "blabla",
    }
    for option in result["data"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)

    # Start flow in advanced mode
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "option1",
        "advanced_no_default",
        "advanced_default",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "advanced_default": "also not default",
            "advanced_no_default": "abc123",
            "option1": "blabla",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "advanced_default": "also not default",
        "advanced_no_default": "abc123",
        "option1": "blabla",
    }
    for option in result["data"]:
        # Make sure we didn't get the Optional or Required instance as key
        assert isinstance(option, str)


async def test_menu_step(hass: HomeAssistant) -> None:
    """Test menu step."""

    MENU_1 = ["option1", "option2"]
    MENU_2 = ["option3", "option4"]

    async def _option1_next_step(_: dict[str, Any]) -> str:
        return "menu2"

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowMenuStep(MENU_1),
        "option1": SchemaFlowFormStep(vol.Schema({}), next_step=_option1_next_step),
        "menu2": SchemaFlowMenuStep(MENU_2),
        "option3": SchemaFlowFormStep(vol.Schema({}), next_step="option4"),
        "option4": SchemaFlowFormStep(vol.Schema({})),
    }

    class TestConfigFlow(MockSchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "option1"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "menu2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "option3"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option3"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option4"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_schema_none(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with schema set to None."""

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="option1"),
        "option1": SchemaFlowFormStep(vol.Schema({}), next_step="pass"),
        "pass": SchemaFlowFormStep(next_step="option3"),
        "option3": SchemaFlowFormStep(vol.Schema({})),
    }

    class TestConfigFlow(MockSchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option3"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_last_step(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with schema set to None."""

    async def _step2_next_step(_: dict[str, Any]) -> str:
        return "step3"

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="step1"),
        "step1": SchemaFlowFormStep(vol.Schema({}), next_step="step2"),
        "step2": SchemaFlowFormStep(vol.Schema({}), next_step=_step2_next_step),
        "step3": SchemaFlowFormStep(vol.Schema({}), next_step=None),
    }

    class TestConfigFlow(MockSchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step1"
        assert result["last_step"] is False

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step2"
        assert result["last_step"] is None

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step3"
        assert result["last_step"] is True

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_next_step_function(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with a next_step function."""

    async def _step1_next_step(_: dict[str, Any]) -> str:
        return "step2"

    async def _step2_next_step(_: dict[str, Any]) -> None:
        return None

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="step1"),
        "step1": SchemaFlowFormStep(vol.Schema({}), next_step=_step1_next_step),
        "step2": SchemaFlowFormStep(vol.Schema({}), next_step=_step2_next_step),
    }

    class TestConfigFlow(MockSchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step2"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_suggested_values(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager
) -> None:
    """Test suggested_values handling in SchemaFlowFormStep."""
    manager.hass = hass

    OPTIONS_SCHEMA = vol.Schema(
        {vol.Optional("option1", default="a very reasonable default"): str}
    )

    async def _validate_user_input(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        if user_input["option1"] == "not a valid value":
            raise SchemaFlowError("option1 not using a valid value")
        return user_input

    async def _step_2_suggested_values(_: SchemaCommonFlowHandler) -> dict[str, Any]:
        return {"option1": "a random override"}

    OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "init": SchemaFlowFormStep(OPTIONS_SCHEMA, next_step="step_1"),
        "step_1": SchemaFlowFormStep(OPTIONS_SCHEMA, next_step="step_2"),
        "step_2": SchemaFlowFormStep(
            OPTIONS_SCHEMA,
            suggested_values=_step_2_suggested_values,
            next_step="step_3",
        ),
        "step_3": SchemaFlowFormStep(
            OPTIONS_SCHEMA, suggested_values=None, next_step="step_4"
        ),
        "step_4": SchemaFlowFormStep(
            OPTIONS_SCHEMA, validate_user_input=_validate_user_input
        ),
    }

    class TestFlow(MockSchemaConfigFlowHandler, domain="test"):
        config_flow = {}
        options_flow = OPTIONS_FLOW

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    config_entry = MockConfigEntry(
        data={},
        domain="test",
        options={"option1": "initial value"},
    )
    config_entry.add_to_hass(hass)

    # Start flow in basic mode, suggested values should be the existing options
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description == {"suggested_value": "initial value"}

    # Go to step 1, suggested values should be the input from init
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blublu"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_1"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description == {"suggested_value": "blublu"}

    # Go to step 2, suggested values should come from the callback function
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_2"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description == {"suggested_value": "a random override"}

    # Go to step 3, suggested values should be empty
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_3"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description is None

    # Go to step 4, suggested values should be the user input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_4"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description == {"suggested_value": "blabla"}

    # Incorrect value in step 4, suggested values should be the user input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "not a valid value"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_4"
    schema_keys: list[vol.Optional] = list(result["data_schema"].schema.keys())
    assert schema_keys == ["option1"]
    assert schema_keys[0].description == {"suggested_value": "not a valid value"}

    # Correct value in step 4, end of flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_options_flow_state(hass: HomeAssistant) -> None:
    """Test flow_state handling in SchemaFlowFormStep."""

    OPTIONS_SCHEMA = vol.Schema(
        {vol.Optional("option1", default="a very reasonable default"): str}
    )

    async def _init_schema(handler: SchemaCommonFlowHandler) -> None:
        handler.flow_state["idx"] = None

    async def _validate_step1_input(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        handler.flow_state["idx"] = user_input["option1"]
        return user_input

    async def _validate_step2_input(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        user_input["idx_from_flow_state"] = handler.flow_state["idx"]
        return user_input

    OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "init": SchemaFlowFormStep(_init_schema, next_step="step_1"),
        "step_1": SchemaFlowFormStep(
            OPTIONS_SCHEMA,
            validate_user_input=_validate_step1_input,
            next_step="step_2",
        ),
        "step_2": SchemaFlowFormStep(
            OPTIONS_SCHEMA,
            validate_user_input=_validate_step2_input,
        ),
    }

    class TestFlow(MockSchemaConfigFlowHandler, domain="test"):
        config_flow = {}
        options_flow = OPTIONS_FLOW

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    config_entry = MockConfigEntry(
        data={},
        domain="test",
        options={"option1": "initial value"},
    )
    config_entry.add_to_hass(hass)

    # Start flow in basic mode, flow state is initialised with None value
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_1"

    options_handler: SchemaOptionsFlowHandler
    options_handler = hass.config_entries.options._progress[result["flow_id"]]
    assert options_handler._common_handler.flow_state == {"idx": None}

    # In step 1, flow state is updated with user input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blublu"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "step_2"

    options_handler = hass.config_entries.options._progress[result["flow_id"]]
    assert options_handler._common_handler.flow_state == {"idx": "blublu"}

    # In step 2, options were updated from flow state
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"option1": "blabla"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "idx_from_flow_state": "blublu",
        "option1": "blabla",
    }


async def test_options_flow_omit_optional_keys(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager
) -> None:
    """Test handling of advanced options in options flow."""
    manager.hass = hass

    OPTIONS_SCHEMA = vol.Schema(
        {
            vol.Optional("optional_no_default"): str,
            vol.Optional("optional_default", default="a very reasonable default"): str,
            vol.Optional("advanced_no_default", description={"advanced": True}): str,
            vol.Optional(
                "advanced_default",
                default="a very reasonable default",
                description={"advanced": True},
            ): str,
        }
    )

    OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
    }

    class TestFlow(MockSchemaConfigFlowHandler, domain="test"):
        config_flow = {}
        options_flow = OPTIONS_FLOW

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    config_entry = MockConfigEntry(
        data={},
        domain="test",
        options={
            "optional_no_default": "abc123",
            "optional_default": "not default",
            "advanced_no_default": "abc123",
            "advanced_default": "not default",
        },
    )
    config_entry.add_to_hass(hass)

    # Start flow in basic mode
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "optional_no_default",
        "optional_default",
    ]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "advanced_default": "not default",
        "advanced_no_default": "abc123",
        "optional_default": "a very reasonable default",
    }

    # Start flow in advanced mode
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert list(result["data_schema"].schema.keys()) == [
        "optional_no_default",
        "optional_default",
        "advanced_no_default",
        "advanced_default",
    ]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "advanced_default": "a very reasonable default",
        "optional_default": "a very reasonable default",
    }
