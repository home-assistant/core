"""Tests for 1-Wire temperature sensor (device family 10, 22, 28, 3B, 42) connected on SysBus."""
from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

from pi1wire import (
    InvalidCRCException,
    NotFoundSensorException,
    UnsupportResponseException,
)

from homeassistant.components.onewire.const import (
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed, mock_registry

MOCK_DEVICE_ID = "28-111111111111"
MOCK_DEVICE_NAME = "My DS18B20"
MOCK_ENTITY_ID = "sensor.my_ds18b20_temperature"


async def test_onewiredirect_setup_valid_device(hass):
    """Test that sysbus config entry works correctly."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": DOMAIN,
            "mount_dir": DEFAULT_SYSBUS_MOUNT_DIR,
            "port": DEFAULT_OWSERVER_PORT,
            "names": {
                MOCK_DEVICE_ID: MOCK_DEVICE_NAME,
            },
        }
    }

    with patch(
        "homeassistant.components.onewire.sensor.Pi1Wire"
    ) as mock_pi1wire, patch("pi1wire.OneWire") as mock_owsensor:
        type(mock_owsensor).mac_address = PropertyMock(
            return_value=MOCK_DEVICE_ID.replace("-", "")
        )
        mock_owsensor.get_temperature.side_effect = [
            25.123,
            FileNotFoundError,
            25.223,
            InvalidCRCException,
            25.323,
            NotFoundSensorException,
            25.423,
            UnsupportResponseException,
            25.523,
        ]
        mock_pi1wire.return_value.find_all_sensors.return_value = [mock_owsensor]
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
        await hass.async_block_till_done()

        assert len(entity_registry.entities) == 1
        registry_entry = entity_registry.entities.get(MOCK_ENTITY_ID)
        assert registry_entry is not None
        assert (
            registry_entry.unique_id == f"/sys/bus/w1/devices/{MOCK_DEVICE_ID}/w1_slave"
        )
        assert registry_entry.unit_of_measurement == TEMP_CELSIUS

        # 25.123
        current_time = datetime.now()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "25.1"

        # FileNotFoundError
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "unknown"

        # 25.223
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "25.2"

        # InvalidCRCException
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "unknown"

        # 25.323
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "25.3"

        # NotFoundSensorException
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "unknown"

        # 25.423
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "25.4"

        # UnsupportResponseException
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "unknown"

        # 25.523
        current_time = current_time + timedelta(minutes=2)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()
        state = hass.states.get(MOCK_ENTITY_ID)
        assert state.state == "25.5"
