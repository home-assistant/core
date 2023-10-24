"""The binary sensor tests for the Airzone Cloud platform."""

from aioairzone_cloud.const import API_OLD_ID

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    # Aidoo
    state = hass.states.get("binary_sensor.bron_problem")
    assert state.state == STATE_OFF
    assert state.attributes.get("errors") is None
    assert state.attributes.get("warnings") is None

    state = hass.states.get("binary_sensor.bron_running")
    assert state.state == STATE_OFF

    # Systems
    state = hass.states.get("binary_sensor.system_1_problem")
    assert state.state == STATE_ON
    assert state.attributes.get("errors") == [
        {
            API_OLD_ID: "error-id",
        },
    ]
    assert state.attributes.get("warnings") is None

    # Zones
    state = hass.states.get("binary_sensor.dormitorio_problem")
    assert state.state == STATE_OFF
    assert state.attributes.get("warnings") is None

    state = hass.states.get("binary_sensor.dormitorio_running")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF
    assert state.attributes.get("warnings") is None

    state = hass.states.get("binary_sensor.salon_running")
    assert state.state == STATE_ON
