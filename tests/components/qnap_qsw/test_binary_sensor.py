"""The binary sensor tests for the QNAP QSW platform."""

from homeassistant.components.qnap_qsw.const import ATTR_MESSAGE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import async_init_integration


async def test_qnap_qsw_create_binary_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.qsw_m408_4c_anomaly")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_MESSAGE) is None

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_1_link")
    assert state.state == STATE_OFF
    entry = entity_registry.async_get(state.entity_id)
    assert entry.unique_id == "qsw_unique_id_ports-status_lacp_port_1_link"

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_2_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_3_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_4_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_5_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_lacp_port_6_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_1_link")
    assert state.state == STATE_ON
    entry = entity_registry.async_get(state.entity_id)
    assert entry.unique_id == "qsw_unique_id_ports-status_port_1_link"

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_2_link")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_3_link")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_4_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_5_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_6_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_7_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_8_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_9_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_10_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_11_link")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.qsw_m408_4c_port_12_link")
    assert state.state == STATE_OFF
