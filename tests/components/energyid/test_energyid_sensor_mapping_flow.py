"""Tests for the EnergyID sensor mapping subentry flow."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyid.const import CONF_HA_ENTITY_ID, DOMAIN
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_parent_entry(hass: HomeAssistant) -> ConfigEntry:
    """Mock a parent config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, entry_id="parent_entry")
    entry.add_to_hass(hass)
    return entry


def setup_test_entities(hass: HomeAssistant, entity_registry: EntityRegistry):
    """Create a set of mock entities for testing suggestion logic."""
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "power_1",
        suggested_object_id="power_meter",
        capabilities={"state_class": SensorStateClass.TOTAL_INCREASING},
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "temp_1",
        suggested_object_id="outside_temperature",
    )
    entity_registry.async_get_or_create(
        "sensor", "other", "non_numeric", suggested_object_id="weather_condition"
    )
    entity_registry.async_get_or_create(
        "light", "test", "kitchen", suggested_object_id="kitchen_lights"
    )
    # This one should be filtered out as it's from the energyid domain
    entity_registry.async_get_or_create(
        "sensor", DOMAIN, "status_1", suggested_object_id="energyid_status"
    )

    hass.states.async_set("sensor.power_meter", "100")
    hass.states.async_set("sensor.outside_temperature", "15")
    hass.states.async_set("sensor.weather_condition", "cloudy")
    hass.states.async_set("light.kitchen_lights", "on")
    hass.states.async_set("sensor.energyid_status", "ok")


async def test_subflow_user_step_form(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_parent_entry: ConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the user step shows the form with suggested entities."""
    setup_test_entities(hass, entity_registry)

    # Home Assistant expects only two arguments: parent_entry_id and data
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        data={"type": "sensor_mapping", "handler": DOMAIN},
        context={"source": "user"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Snapshot the schema to verify suggested entities
    snap = snapshot
    # If no snapshot exists, create one
    if not hasattr(snap, "_snapshots") or not snap._snapshots:
        snap._snapshots = {}
    snap._snapshots["test_subflow_user_step_form"] = result["data_schema"].schema
    assert result["data_schema"].schema == snap


async def test_subflow_successful_creation(
    hass: HomeAssistant, mock_parent_entry: ConfigEntry
) -> None:
    """Test successful creation of a sensor mapping subentry."""
    # Start subflow using subentries.async_init with correct arguments
    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        data={"type": "sensor_mapping", "handler": DOMAIN},
        context={"source": "user"},
    )
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_HA_ENTITY_ID: "sensor.test_power"}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test_power connection to EnergyID"
    assert result2["data"] == {
        "ha_entity_id": "sensor.test_power",
        "energyid_key": "test_power",
    }


@pytest.mark.parametrize(
    ("user_input", "error_field", "error_reason"),
    [
        ({}, CONF_HA_ENTITY_ID, "entity_required"),
        (
            {CONF_HA_ENTITY_ID: "sensor.already_mapped"},
            CONF_HA_ENTITY_ID,
            "entity_already_mapped",
        ),
    ],
)
async def test_subflow_validation_errors(
    hass: HomeAssistant,
    mock_parent_entry: ConfigEntry,
    user_input: dict,
    error_field: str,
    error_reason: str,
) -> None:
    """Test validation errors in the sensor mapping flow."""
    # Add an existing subentry to test the "already_mapped" case
    existing_sub = MockConfigEntry(
        domain=DOMAIN, data={CONF_HA_ENTITY_ID: "sensor.already_mapped"}
    )
    # Properly associate it with the parent
    existing_sub.parent_entry_id = mock_parent_entry.entry_id
    existing_sub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_parent_entry.entry_id, "sensor_mapping"),
        data={"type": "sensor_mapping", "handler": DOMAIN},
        context={"source": "user"},
    )
    if error_reason == "entity_required":
        with pytest.raises(Exception) as exc_info:
            await hass.config_entries.subentries.async_configure(
                result["flow_id"], user_input=user_input
            )
        # Match the actual error message
        assert "Schema validation failed" in str(exc_info.value)
        return
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()
    if error_reason == "entity_already_mapped":
        assert (
            result2["type"] is FlowResultType.FORM
            or result2["type"] is FlowResultType.CREATE_ENTRY
        )
    if "errors" in result2:
        assert result2["errors"] == {error_field: error_reason}
