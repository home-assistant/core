"""The tests for Kira sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.kira import remote as kira
from homeassistant.core import HomeAssistant

SERVICE_SEND_COMMAND = "send_command"

TEST_CONFIG = {kira.DOMAIN: {"devices": [{"host": "127.0.0.1", "port": 17324}]}}

DISCOVERY_INFO = {"name": "kira", "device": "kira"}

DEVICES = []


def add_entities(devices):
    """Mock add devices."""
    for device in devices:
        DEVICES.append(device)


def test_service_call(hass: HomeAssistant) -> None:
    """Test Kira's ability to send commands."""
    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_REMOTE: {}}
    hass.data[kira.DOMAIN][kira.CONF_REMOTE]["kira"] = mock_kira

    kira.setup_platform(hass, TEST_CONFIG, add_entities, DISCOVERY_INFO)
    assert len(DEVICES) == 1
    remote = DEVICES[0]

    assert remote.name == "kira"

    command = ["FAKE_COMMAND"]
    device = "FAKE_DEVICE"
    commandTuple = (command[0], device)
    remote.send_command(device=device, command=command)

    mock_kira.sendCode.assert_called_with(commandTuple)
