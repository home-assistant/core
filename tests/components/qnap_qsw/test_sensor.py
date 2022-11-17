"""The sensor tests for the QNAP QSW platform."""

from unittest.mock import AsyncMock

from homeassistant.components.qnap_qsw.const import ATTR_MAX
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_qnap_qsw_create_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
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
