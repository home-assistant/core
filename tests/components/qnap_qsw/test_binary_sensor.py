"""The binary sensor tests for the QNAP QSW platform."""

from homeassistant.const import STATE_OFF

from .util import async_init_integration


async def test_qnap_qsw_create_binary_sensors(hass):
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.qsw_m408_4c_condition_anomaly")
    assert state.state == STATE_OFF
    assert state.attributes["condition_message"] is None

    state = hass.states.get("binary_sensor.qsw_m408_4c_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes["current_version"] == "1.0.12.17336"
    assert state.attributes["newest_version"] is None
