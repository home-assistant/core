"""Test schema_config_entry_flow."""
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    wrapped_entity_config_entry_title,
)
from homeassistant.util.decorator import Registry

from tests.common import MockConfigEntry


@pytest.fixture
def manager():
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
    mgr.mock_created_entries = entries
    mgr.mock_reg_handler = handlers.register
    return mgr


async def test_name(hass: HomeAssistant) -> None:
    """Test the config flow name is copied from registry entry, with fallback to state."""
    registry = er.async_get(hass)
    entity_id = "switch.ceiling"

    # No entry or state, use Object ID
    assert wrapped_entity_config_entry_title(hass, entity_id) == "ceiling"

    # State set, use name from state
    hass.states.async_set(entity_id, "on", {"friendly_name": "State Name"})
    assert wrapped_entity_config_entry_title(hass, entity_id) == "State Name"

    # Entity registered, use original name from registry entry
    hass.states.async_remove(entity_id)
    entry = registry.async_get_or_create(
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
    registry.async_update_entity("switch.ceiling", name="Custom Name")
    assert wrapped_entity_config_entry_title(hass, entity_id) == "Custom Name"
    assert wrapped_entity_config_entry_title(hass, entry.id) == "Custom Name"


@pytest.mark.parametrize("marker", (vol.Required, vol.Optional))
async def test_config_flow_advanced_option(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager, marker
):
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
    class TestFlow(SchemaConfigFlowHandler):
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


@pytest.mark.parametrize("marker", (vol.Required, vol.Optional))
async def test_options_flow_advanced_option(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager, marker
):
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

    class TestFlow(SchemaConfigFlowHandler, domain="test"):
        config_flow = {}
        options_flow = OPTIONS_FLOW

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
