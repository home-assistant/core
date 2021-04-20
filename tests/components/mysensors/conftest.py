"""Provide common mysensors fixtures."""
import pytest

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN


@pytest.fixture(name="mqtt")
async def mock_mqtt_fixture(hass):
    """Mock the MQTT integration."""
    hass.config.components.add(MQTT_DOMAIN)
