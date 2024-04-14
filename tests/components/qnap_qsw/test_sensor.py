"""The sensor tests for the QNAP QSW platform."""

from homeassistant.components.qnap_qsw.const import ATTR_MAX
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_qnap_qsw_create_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.qsw_m408_4c_fan_1_speed")
    assert state.state == "1991"

    state = hass.states.get("sensor.qsw_m408_4c_fan_2_speed")
    assert state is None

    state = hass.states.get("sensor.qsw_m408_4c_ports")
    assert state.state == "3"
    assert state.attributes.get(ATTR_MAX) == 12

    state = hass.states.get("sensor.qsw_m408_4c_rx_errors")
    assert state.state == "22"

    state = hass.states.get("sensor.qsw_m408_4c_rx")
    assert state.state == "22200"

    state = hass.states.get("sensor.qsw_m408_4c_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_temperature")
    assert state.state == "31"
    assert state.attributes.get(ATTR_MAX) == 85

    state = hass.states.get("sensor.qsw_m408_4c_tx")
    assert state.state == "11100"

    state = hass.states.get("sensor.qsw_m408_4c_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_uptime")
    assert state.state == "91"

    # LACP Ports
    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_1_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_2_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_3_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_4_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_5_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_link_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_lacp_port_6_tx_speed")
    assert state.state == "0"

    # Ports
    state = hass.states.get("sensor.qsw_m408_4c_port_1_link_speed")
    assert state.state == "10000"

    state = hass.states.get("sensor.qsw_m408_4c_port_1_rx")
    assert state.state == "20000"

    state = hass.states.get("sensor.qsw_m408_4c_port_1_rx_errors")
    assert state.state == "20"

    state = hass.states.get("sensor.qsw_m408_4c_port_1_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_1_tx")
    assert state.state == "10000"

    state = hass.states.get("sensor.qsw_m408_4c_port_1_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_rx")
    assert state.state == "2000"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_rx_errors")
    assert state.state == "2"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_tx")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_2_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_link_speed")
    assert state.state == "100"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_rx")
    assert state.state == "200"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_tx")
    assert state.state == "100"

    state = hass.states.get("sensor.qsw_m408_4c_port_3_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_4_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_5_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_6_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_7_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_8_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_9_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_10_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_11_tx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_link_speed")
    assert state.state == "1000"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_rx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_rx_errors")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_rx_speed")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_tx")
    assert state.state == "0"

    state = hass.states.get("sensor.qsw_m408_4c_port_12_tx_speed")
    assert state.state == "0"
