"""The tests for Kira sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.kira import sensor as kira
from homeassistant.core import HomeAssistant

from tests.common import MockEntityPlatform

TEST_CONFIG = {kira.DOMAIN: {"sensors": [{"host": "127.0.0.1", "port": 17324}]}}

DISCOVERY_INFO = {"name": "kira", "device": "kira"}

DEVICES = []


def add_entities(devices):
    """Mock add devices."""
    DEVICES.extend(devices)


@patch("homeassistant.components.kira.sensor.KiraReceiver.schedule_update_ha_state")
def test_kira_sensor_callback(
    mock_schedule_update_ha_state, hass: HomeAssistant
) -> None:
    """Ensure Kira sensor properly updates its attributes from callback."""
    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_SENSOR: {}}
    hass.data[kira.DOMAIN][kira.CONF_SENSOR]["kira"] = mock_kira

    kira.setup_platform(hass, TEST_CONFIG, add_entities, DISCOVERY_INFO)
    assert len(DEVICES) == 1
    sensor = DEVICES[0]
    sensor.hass = hass
    sensor.platform = MockEntityPlatform(hass)

    assert sensor.name == "kira"

    codeName = "FAKE_CODE"
    deviceName = "FAKE_DEVICE"
    codeTuple = (codeName, deviceName)
    sensor._update_callback(codeTuple)

    mock_schedule_update_ha_state.assert_called()

    assert sensor.state == codeName
    assert sensor.extra_state_attributes == {kira.CONF_DEVICE: deviceName}
