"""The sensor tests for the Airzone platform."""

from aioairzone.const import API_ERROR_LOW_BATTERY
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    # Systems
    state = hass.states.get("binary_sensor.system_1_problem")
    assert state.state == STATE_OFF

    # Zones
    state = hass.states.get("binary_sensor.despacho_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.despacho_battery")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.despacho_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.despacho_problem")
    assert state.state == STATE_ON
    assert state.attributes.get("errors") == [API_ERROR_LOW_BATTERY]

    state = hass.states.get("binary_sensor.dorm_1_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_battery")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_battery")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.dorm_2_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_air_demand")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.dorm_ppal_battery")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_floor_demand")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.dorm_ppal_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_anti_freeze")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_anti_freeze")
    assert state.state == STATE_OFF

    # Cold/heat/generic demand binary sensors are disabled by default.
    state = hass.states.get("binary_sensor.dorm_ppal_demand")
    assert state is None

    state = hass.states.get("binary_sensor.dorm_ppal_heat_demand")
    assert state is None

    state = hass.states.get("binary_sensor.salon_battery")
    assert state is None

    state = hass.states.get("binary_sensor.salon_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.airzone_2_1_battery")
    assert state is None

    state = hass.states.get("binary_sensor.airzone_2_1_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dkn_plus_battery")
    assert state is None

    state = hass.states.get("binary_sensor.dkn_plus_problem")
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_create_binary_sensors_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    """Test creation of binary sensors that are disabled by default."""

    await async_init_integration(hass)

    # Generic demand (air OR floor demand).
    state = hass.states.get("binary_sensor.salon_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_demand")
    assert state.state == STATE_ON

    # Cold demand.
    state = hass.states.get("binary_sensor.salon_cold_demand")
    assert state.state == STATE_OFF

    # Heat demand.
    state = hass.states.get("binary_sensor.salon_heat_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_heat_demand")
    assert state.state == STATE_ON
