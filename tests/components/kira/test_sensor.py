"""The tests for Kira sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.kira import sensor as kira
from homeassistant.core import HomeAssistant

TEST_CONFIG = {kira.DOMAIN: {"sensors": [{"host": "127.0.0.1", "port": 17324}]}}
DISCOVERY_INFO = {"name": "kira", "device": "kira"}


async def test_kira_sensor(hass: HomeAssistant):
    """Tests the Kira Sensor platform."""

    DEVICES = []

    def add_entities(devices):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            DEVICES.append(device)

    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_SENSOR: {}}
    hass.data[kira.DOMAIN][kira.CONF_SENSOR]["kira"] = mock_kira
    kira.setup_platform(hass, TEST_CONFIG, add_entities, DISCOVERY_INFO)
    assert len(DEVICES) == 1
    sensor = DEVICES[0]
    sensor.name == "kira"
    sensor.hass = hass

    code_name = "FAKE_CODE"
    device_name = "FAKE_DEVICE"
    sensor._update_callback((code_name, device_name))
    assert sensor.state == code_name
    assert sensor.extra_state_attributes == {kira.CONF_DEVICE: device_name}
