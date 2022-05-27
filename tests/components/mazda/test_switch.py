"""The switch tests for the Mazda Connected Services integration."""

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_switch_setup(hass):
    """Test setup of the switch entity."""
    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("switch.my_mazda3_charging")
    assert entry
    assert entry.unique_id == "JM000000000000000"

    state = hass.states.get("switch.my_mazda3_charging")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Charging"
    assert state.attributes.get(ATTR_ICON) == "mdi:ev-station"

    assert state.state == STATE_ON


async def test_start_charging(hass):
    """Test turning on the charging switch."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    client_mock.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_mazda3_charging"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.start_charging.assert_called_once()
    client_mock.refresh_vehicle_status.assert_called_once()
    client_mock.get_vehicle_status.assert_called_once()
    client_mock.get_ev_vehicle_status.assert_called_once()


async def test_stop_charging(hass):
    """Test turning off the charging switch."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    client_mock.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_mazda3_charging"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.stop_charging.assert_called_once()
    client_mock.refresh_vehicle_status.assert_called_once()
    client_mock.get_vehicle_status.assert_called_once()
    client_mock.get_ev_vehicle_status.assert_called_once()
