"""Tests for the TechnoVE sensor platform."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_technove")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the TechnoVE sensors."""
    mock_config_entry.add_to_hass(hass)

    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch(
        "homeassistant.components.technove.sensor.utcnow", return_value=test_time
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.technove_station_estimated_current"))
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfElectricCurrent.MILLIAMPERE
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert state.state == "470"

    assert (
        entry := entity_registry.async_get("sensor.technove_station_estimated_current")
    )
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_estimated_current"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_uptime"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-11-11T09:10:00+00:00"

    assert (entry := entity_registry.async_get("sensor.technove_station_uptime"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_uptime"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_free_memory"))
    assert state.attributes.get(ATTR_ICON) == "mdi:memory"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfInformation.BYTES
    assert state.state == "14600"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (entry := entity_registry.async_get("sensor.technove_station_free_memory"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_free_heap"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_wi_fi_signal"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "76"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (entry := entity_registry.async_get("sensor.technove_station_wi_fi_signal"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_wifi_signal"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_wi_fi_rssi"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SIGNAL_STRENGTH
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert state.state == "-62"

    assert (entry := entity_registry.async_get("sensor.technove_station_wi_fi_rssi"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_wifi_rssi"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_wi_fi_channel"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "11"

    assert (entry := entity_registry.async_get("sensor.technove_station_wi_fi_channel"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_wifi_channel"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_wi_fi_bssid"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "AA:AA:AA:AA:AA:BB"

    assert (entry := entity_registry.async_get("sensor.technove_station_wi_fi_bssid"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_wifi_bssid"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.technove_station_ip"))
    assert state.attributes.get(ATTR_ICON) == "mdi:ip-network"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "127.0.0.1"

    assert (entry := entity_registry.async_get("sensor.technove_station_ip"))
    assert entry.unique_id == "AA:AA:AA:AA:AA:BB_ip"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.technove_station_wi_fi_rssi",
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
