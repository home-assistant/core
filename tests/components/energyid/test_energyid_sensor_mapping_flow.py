"""Test EnergyID sensor mapping subentry flow."""

import pytest

from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_UUID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


# This fixture ensures the energyid component is loaded, which is required for sub-flows.
@pytest.fixture(autouse=True)
async def setup_energyid_integration(hass: HomeAssistant):
    """Set up the EnergyID integration to handle sub-flows."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture
def mock_parent_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock parent config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock Title",
        data={
            "provisioning_key": "test_key",
            "provisioning_secret": "test_secret",
            "device_id": "test_device",
            "device_name": "Test Device",
        },
        entry_id="parent_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


async def test_subflow_user_step_form(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test that the user step shows the form correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "ha_entity_id" in result["data_schema"].schema


async def test_subflow_successful_creation(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful creation of a sensor mapping subentry."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_2", suggested_object_id="test_power"
    )
    hass.states.async_set("sensor.test_power", "50")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ha_entity_id": entity_entry.entity_id}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test_power connection to EnergyID"
    assert result2["data"][CONF_HA_ENTITY_UUID] == entity_entry.id
    assert result2["data"][CONF_ENERGYID_KEY] == "test_power"


async def test_subflow_entity_already_mapped(
    hass: HomeAssistant,
    mock_parent_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test error when entity is already mapped."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "power_3", suggested_object_id="already_mapped"
    )
    hass.states.async_set("sensor.already_mapped", "75")

    # This sub-entry "already exists" for the parent
    sub_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HA_ENTITY_UUID: entity_entry.id,
            CONF_ENERGYID_KEY: "already_mapped",
        },
        entry_id="sub_entry_1",
    )
    sub_entry.parent_entry_id = mock_parent_entry.entry_id
    sub_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ha_entity_id": entity_entry.entity_id}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "entity_already_mapped"


async def test_subflow_entity_not_found(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test error when entity is not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ha_entity_id": "sensor.nonexistent"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "entity_not_found"


async def test_subflow_no_entity_selected(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test error when no entity is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ha_entity_id": ""}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "entity_required"


async def test_subflow_empty_user_input(
    hass: HomeAssistant, mock_parent_entry: MockConfigEntry
) -> None:
    """Test subflow with empty user input shows form again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "sensor_mapping", "entry_id": mock_parent_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ha_entity_id": ""}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "entity_required"
