"""The sensor tests for the QNAP QSW platform."""

from .util import async_init_integration


async def test_qnap_qsw_create_sensors(hass):
    """Test creation of sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.qsw_m408_4c_fan_1_speed")
    assert state.state == "2005"

    state = hass.states.get("sensor.qsw_m408_4c_mac_address")
    assert state.state == "24:5E:BE:00:00:00"

    state = hass.states.get("sensor.qsw_m408_4c_network_in")
    assert state.state == "2095.328"
    assert state.attributes["errors"] == 0

    state = hass.states.get("sensor.qsw_m408_4c_network_out")
    assert state.state == "134.028"

    state = hass.states.get("sensor.qsw_m408_4c_ports")
    assert state.state == "2"
    assert state.attributes["full_duplex"] == 2
    assert state.attributes["half_duplex"] == 0
    assert state.attributes["speed_10"] == 0
    assert state.attributes["speed_100"] == 1
    assert state.attributes["speed_1000"] == 1
    assert state.attributes["speed_2500"] == 0
    assert state.attributes["speed_5000"] == 0
    assert state.attributes["speed_10000"] == 0
    assert state.attributes["total"] == 12

    state = hass.states.get("sensor.qsw_m408_4c_temperature")
    assert state.state == "39"
    assert state.attributes["maximum"] == 85

    state = hass.states.get("sensor.qsw_m408_4c_throughput_network_in")
    assert state.state == "0.0"

    state = hass.states.get("sensor.qsw_m408_4c_throughput_network_out")
    assert state.state == "0.0"

    state = hass.states.get("sensor.qsw_m408_4c_uptime")
    assert state.state is not None
    assert state.attributes["seconds"] == 60
