"""The binary sensor tests for the QNAP QSW platform."""

from homeassistant.components.qnap_qsw.const import ATTR_MESSAGE
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_qnap_qsw_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.qsw_m408_4c_anomaly")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_MESSAGE) is None
