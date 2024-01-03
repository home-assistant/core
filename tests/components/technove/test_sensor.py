"""Tests for the TechnoVE sensor platform."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_technove")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the TechnoVE sensors."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.technove_station_current"))
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricCurrent.AMPERE
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert state.state == "23.75"

    assert (entry := entity_registry.async_get("sensor.technove_station_current"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_current"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_signal_strength"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SIGNAL_STRENGTH
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert state.state == "-82"

    assert (
        entry := entity_registry.async_get("sensor.technove_station_signal_strength")
    )
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_rssi"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_wi_fi_network_name"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "Connecting..."

    assert (
        entry := entity_registry.async_get("sensor.technove_station_wi_fi_network_name")
    )
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_ssid"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_status"))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "plugged_charging"

    assert (entry := entity_registry.async_get("sensor.technove_station_status"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_status"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.technove_station_signal_strength",
        "sensor.technove_station_wi_fi_network_name",
    ),
)
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default TechnoVE sensors."""
    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_wifi_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_technove: MagicMock,
) -> None:
    """Test missing Wi-Fi information from TechnoVE device."""
    # Remove Wi-Fi info
    device = mock_technove.update.return_value
    device.info.network_ssid = None

    # Setup
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.technove_station_wi_fi_network_name"))
    assert state.state == STATE_UNKNOWN
