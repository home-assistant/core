"""Test the LibreHardwareMonitor sensor."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from librehardwaremonitor_api import LibreHardwareMonitorConnectionError

from homeassistant.components.librehardwaremonitor.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import async_fire_time_changed


async def test_sensors_are_created(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are created."""
    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"
    await init_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "39.4"
    assert state.attributes
    assert state.attributes.get("min_value") == "37.4"
    assert state.attributes.get("max_value") == "73.0"
    assert state.attributes.get("unit_of_measurement") == "°C"

    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError()

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_lhm_client.get_data.side_effect = None

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "39.4"


async def test_sensors_are_updated(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are updated."""
    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"
    await init_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "39.4"

    updated_data = copy.deepcopy(mock_lhm_client.get_data.return_value)
    updated_data.sensor_data["amdcpu-0-temperature-3"].value = "42,1"
    mock_lhm_client.get_data.return_value = updated_data

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "42.1"

    mock_lhm_client.reset_mock()


async def test_sensor_state_is_unknown_when_lhm_indicates_missing_value(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test sensor state is unknown when no value is present."""
    entity_id = "sensor.msi_mag_b650m_mortar_wifi_ms_7d76_system_fan_1_fan"
    await init_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.name == "MSI MAG B650M MORTAR WIFI (MS-7D76) System Fan #1 Fan"


async def test_sensor_state_is_unknown_when_no_sensor_data_is_provided(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor state is unknown when sensor data is missing."""
    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"
    await init_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "39.4"

    del mock_lhm_client.get_data.return_value.sensor_data["amdcpu-0-temperature-3"]

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
