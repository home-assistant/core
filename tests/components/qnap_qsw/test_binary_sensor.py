"""The binary sensor tests for the QNAP QSW platform."""

from homeassistant.const import STATE_OFF

from .util import async_init_integration


async def test_qnap_qsw_create_binary_sensors(hass):
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.qsw_m408_4c_anomaly")
    assert state.state == STATE_OFF
    assert state.attributes["message"] is None

    state = hass.states.get("binary_sensor.qsw_m408_4c_update")
    assert state.state == STATE_OFF
    assert state.attributes["current_timestamp"] == "2021-05-06T10:10:19+08:00"
    assert state.attributes["current_version"] == "1.0.12.17336"
    assert (
        state.attributes["download_url"]
        == "https://download.qnap.com/Storage/Networking/QSW408FW/QSW-M408AC3-FW.v1.0.12_S20210506_17336.img"
    )
    assert state.attributes["latest_version"] is None
