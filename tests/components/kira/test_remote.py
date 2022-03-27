"""The tests for Kira sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.kira import remote as kira
from homeassistant.core import HomeAssistant

TEST_CONFIG = {kira.DOMAIN: {"devices": [{"host": "127.0.0.1", "port": 17324}]}}
DISCOVERY_INFO = {"name": "kira", "device": "kira"}


async def test_service_call(hass: HomeAssistant):
    """Test Kira's ability to send commands."""

    DEVICES = []

    def add_entities(devices):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            DEVICES.append(device)

    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_REMOTE: {}}
    hass.data[kira.DOMAIN][kira.CONF_REMOTE]["kira"] = mock_kira
    kira.setup_platform(hass, TEST_CONFIG, add_entities, DISCOVERY_INFO)

    assert len(DEVICES) == 1
    remote = DEVICES[0]
    assert remote.name == "kira"

    command = ["FAKE_COMMAND"]
    device = "FAKE_DEVICE"
    remote.send_command(device=device, command=command)
    mock_kira.sendCode.assert_called_with((command[0], device))
