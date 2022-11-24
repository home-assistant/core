"""The binary sensor tests for the QNAP QSW platform."""

from spencerassistant.components.qnap_qsw.const import ATTR_MESSAGE
from spencerassistant.const import STATE_OFF
from spencerassistant.core import spencerAssistant

from .util import async_init_integration


async def test_qnap_qsw_create_binary_sensors(hass: spencerAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.qsw_m408_4c_anomaly")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_MESSAGE) is None
