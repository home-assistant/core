"""The tests for Kira sensor platform."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.kira import sensor as kira

TEST_CONFIG = {kira.DOMAIN: {"sensors": [{"host": "127.0.0.1", "port": 17324}]}}

DISCOVERY_INFO = {"name": "kira", "device": "kira"}

ENTITY_ID = "kira.entity_id"

DEVICES = []


def add_entities(devices):
    """Mock add devices."""
    for device in devices:
        device.entity_id = ENTITY_ID
        DEVICES.append(device)


@pytest.fixture
def configured_kira(hass):
    """Configure kira platform."""
    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_SENSOR: {}}
    hass.data[kira.DOMAIN][kira.CONF_SENSOR]["kira"] = mock_kira
    kira.setup_platform(hass, TEST_CONFIG, add_entities, DISCOVERY_INFO)


def test_kira_sensor_callback(hass, configured_kira):
    """Ensure Kira sensor properly updates its attributes from callback."""
    assert len(DEVICES) == 1
    sensor = DEVICES[0]

    assert sensor.name == "kira"

    sensor.hass = hass

    codeName = "FAKE_CODE"
    deviceName = "FAKE_DEVICE"
    codeTuple = (codeName, deviceName)
    sensor._update_callback(codeTuple)

    assert sensor.state == codeName
    assert sensor.extra_state_attributes == {kira.CONF_DEVICE: deviceName}
