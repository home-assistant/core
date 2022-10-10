"""SNMP sensor tests."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def hlapi_mock():
    """Mock out 3rd party API."""
    mock_data = MagicMock()
    mock_data.prettyPrint = Mock(return_value="hello")
    with patch(
        "homeassistant.components.snmp.sensor.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        yield


async def test_basic_config(hass: HomeAssistant) -> None:
    """Test basic entity configuration."""

    config = {
        SENSOR_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    }

    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.snmp")
    assert state.state == "hello"
    assert state.attributes == {"friendly_name": "SNMP"}


async def test_entity_config(hass: HomeAssistant) -> None:
    """Test entity configuration."""

    config = {
        SENSOR_DOMAIN: {
            # SNMP configuration
            "platform": "snmp",
            "host": "192.168.1.32",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            # Entity configuration
            "icon": "{{'mdi:one_two_three'}}",
            "picture": "{{'blabla.png'}}",
            "device_class": "temperature",
            "name": "{{'SNMP' + ' ' + 'Sensor'}}",
            "state_class": "measurement",
            "unique_id": "very_unique",
            "unit_of_measurement": "beardsecond",
        },
    }

    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("sensor.snmp_sensor").unique_id == "very_unique"

    state = hass.states.get("sensor.snmp_sensor")
    assert state.state == "hello"
    assert state.attributes == {
        "device_class": "temperature",
        "entity_picture": "blabla.png",
        "friendly_name": "SNMP Sensor",
        "icon": "mdi:one_two_three",
        "state_class": "measurement",
        "unit_of_measurement": "beardsecond",
    }
