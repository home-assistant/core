"""The tests for Kira sensor platform."""

from homeassistant.components.kira import sensor as kira


def test_kira_sensor_callback(hass, configured_kira, fake_entities):
    """Ensure Kira sensor properly updates its attributes from callback."""
    devices = fake_entities.devices
    assert len(devices) == 1
    sensor = devices[0]

    assert sensor.name == "kira"

    sensor.hass = hass

    codeName = "FAKE_CODE"
    deviceName = "FAKE_DEVICE"
    codeTuple = (codeName, deviceName)
    sensor._update_callback(codeTuple)

    assert sensor.state == codeName
    assert sensor.extra_state_attributes == {kira.CONF_DEVICE: deviceName}
