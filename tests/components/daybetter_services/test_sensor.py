"""Test the DayBetter Services sensor platform."""

from datetime import timedelta

import pytest

from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_sensor_setup(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test sensor setup."""
    _, _, _ = init_integration

    temp_entity_id = "sensor.test_group_temperature"
    humi_entity_id = "sensor.test_group_humidity"

    temp_state = hass.states.get(temp_entity_id)
    humi_state = hass.states.get(humi_entity_id)

    assert temp_state is not None
    assert humi_state is not None
    assert temp_state.state == "22.5"
    assert humi_state.state == "65.0"


async def test_sensor_attributes(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test sensor attributes."""
    _, _, _ = init_integration

    temp_entity_id = "sensor.test_group_temperature"
    humi_entity_id = "sensor.test_group_humidity"

    temp_sensor_state = hass.states.get(temp_entity_id)
    humidity_sensor_state = hass.states.get(humi_entity_id)
    assert temp_sensor_state is not None
    assert humidity_sensor_state is not None
    assert (
        temp_sensor_state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    )
    assert temp_sensor_state.attributes["device_class"] == "temperature"
    assert temp_sensor_state.attributes["state_class"] == "measurement"

    assert humidity_sensor_state.attributes["unit_of_measurement"] == PERCENTAGE
    assert humidity_sensor_state.attributes["device_class"] == "humidity"
    assert humidity_sensor_state.attributes["state_class"] == "measurement"


@pytest.mark.parametrize(
    "init_integration",
    [{"payload": []}],
    indirect=True,
)
async def test_sensor_no_devices(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test sensor setup with no devices."""
    assert not hass.states.async_entity_ids("sensor")


@pytest.mark.parametrize(
    "init_integration",
    [{"payload": []}],
    indirect=True,
)
async def test_sensor_wrong_device_type(
    hass: HomeAssistant, init_integration: tuple
) -> None:
    """Test sensor setup with wrong device type (non-sensor PID)."""
    assert not hass.states.async_entity_ids("sensor")


async def test_sensor_update(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test sensor data update."""
    _, mock_fetch, _ = init_integration

    temp_entity_id = "sensor.test_group_temperature"
    humi_entity_id = "sensor.test_group_humidity"

    temp_state = hass.states.get(temp_entity_id)
    assert temp_state is not None
    assert temp_state.state == "22.5"

    mock_fetch.return_value = [
        {
            "deviceId": "test_device_1",
            "deviceName": "test_sensor",
            "deviceGroupName": "Test Group",
            "deviceMoldPid": "pid1",
            "type": 5,
            "temp": 250,
            "humi": 700,
        }
    ]

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=300),
    )
    await hass.async_block_till_done()

    updated_temp_state = hass.states.get(temp_entity_id)
    updated_humi_state = hass.states.get(humi_entity_id)

    assert updated_temp_state is not None
    assert updated_humi_state is not None
    assert updated_temp_state.state == "25.0"
    assert updated_humi_state.state == "70.0"
    assert mock_fetch.await_count >= 2
