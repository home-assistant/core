"""Tests for 1-Wire device type HobbyBoards_EF (family EF)."""
from unittest.mock import patch

from homeassistant import util
from homeassistant.components.onewire.const import DEFAULT_OWSERVER_PORT
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

DEVICE_ID = "EF.111111111111"
DEVICE_NAME = "My HobbyBoards_EF"
DEVICE_TYPE = "HobbyBoards_EF"


async def test_setup_owserver(hass):
    """Test a hobbyboard (HobbyBoards_EF) on OWServer."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": "onewire",
            "host": "localhost",
            "port": DEFAULT_OWSERVER_PORT,
            "names": {
                DEVICE_ID: DEVICE_NAME,
            },
        }
    }
    with patch(
        "homeassistant.components.onewire.sensor.protocol.proxy",
    ) as owproxy:
        owproxy.return_value.dir.return_value = [f"/{DEVICE_ID}/"]
        owproxy.return_value.read.side_effect = [
            DEVICE_ID[0:2].encode(),
            DEVICE_TYPE.encode(),  # read the type
            b"    67.745",  # read the humidity
            b"    65.541",  # read the humidity_raw
            b"    25.123",  # read the temperature
        ]
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 3

    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_humidity"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None

    state = hass.states.get(sensor_id)
    assert state.state == "67.7"

    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_humidity_raw"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None

    state = hass.states.get(sensor_id)
    assert state.state == "65.5"

    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_temperature"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None

    state = hass.states.get(sensor_id)
    assert state.state == "25.1"
