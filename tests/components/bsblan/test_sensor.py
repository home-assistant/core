"""Tests for the BSB-LAN sensor platform."""

from unittest.mock import AsyncMock

from bsblan import BSBLANError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_with_selected_platforms

ENTITY_CURRENT_TEMP = "sensor.heating_circuit_1_temperature"
ENTITY_OUTSIDE_TEMP = "sensor.bsb_lan_outside_temperature"
ENTITY_TOTAL_ENERGY = "sensor.bsb_lan_total_energy"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_not_created_when_data_unavailable(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are not created when sensor data is not available."""
    # Set all sensor data to None to simulate no sensors available
    mock_bsblan.state.return_value.current_temperature = None
    mock_bsblan.sensor.return_value.outside_temperature = None
    mock_bsblan.sensor.return_value.total_energy = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should not create any sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 0


async def test_partial_sensors_created_when_some_data_available(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only available sensors are created when some sensor data is available."""
    # Without outside temperature and energy, the sensor section has nothing to read
    mock_bsblan.sensor.side_effect = BSBLANError(
        "None of the requested parameters are valid for this section"
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should create only the current temperature sensor
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 1
    assert sensor_entities[0].entity_id == ENTITY_CURRENT_TEMP


async def test_current_temperature_per_circuit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry_dual_circuit: MockConfigEntry,
) -> None:
    """Test each heating circuit gets its own current temperature sensor."""
    await setup_with_selected_platforms(
        hass, mock_config_entry_dual_circuit, [Platform.SENSOR]
    )

    for entity_id in (
        "sensor.heating_circuit_1_temperature",
        "sensor.heating_circuit_2_temperature",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "18.6"


async def test_current_temperature_keeps_entity_id(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the existing current temperature sensor moves to circuit 1."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "00:80:41:19:69:90-current_temperature",
        suggested_object_id="bsb_lan_current_temperature",
        config_entry=mock_config_entry,
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    entry = entity_registry.async_get("sensor.bsb_lan_current_temperature")
    assert entry is not None
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:80:41:19:69:90-circuit-1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert entry.device_id == device.id
