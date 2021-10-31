"""The sensor tests for the QNAP QSW platform."""

from .util import async_init_integration


async def test_qnap_qsw_create_sensors(hass):
    """Test creation of sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.qsw_m408_4c_fan_1_speed")
    assert state.state == "2005"

    state = hass.states.get("sensor.qsw_m408_4c_mac_address")
    assert state.state == "24:5E:BE:00:00:00"

    state = hass.states.get("sensor.qsw_m408_4c_temperature")
    assert state.state == "39"

    state = hass.states.get("sensor.qsw_m408_4c_maximum_temperature")
    assert state.state == "85"

    state = hass.states.get("sensor.qsw_m408_4c_uptime")
    assert state is not None
    assert state.attributes["uptime_seconds"] == 60
