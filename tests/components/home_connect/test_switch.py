"""Tests for home_connect switch entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from homeconnect import HomeConnectAPI

from homeassistant.components.home_connect.const import (
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_OPERATION_STATE,
    BSH_POWER_STATE,
    DOMAIN,
    SIGNAL_UPDATE_ENTITIES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .conftest import get_appliances

from tests.common import MockConfigEntry

TEST_HC_APP = "Oven"


async def test_switch(
    bypass_throttle,
    platforms,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    problematic_appliance,
) -> None:
    """Test switch entities."""
    platforms = [Platform.SWITCH]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    with patch.object(
        HomeConnectAPI,
        "get_appliances",
        side_effect=lambda: get_appliances(hass.data[DOMAIN][config_entry.entry_id]),
    ):
        assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    (hc_app,) = (
        x["device"].appliance
        for x in hass.data[DOMAIN][config_entry.entry_id].devices
        if x["device"].appliance.type == TEST_HC_APP
    )
    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "on")
    assert hass.states.is_state("switch.oven_program_hotair", "on")

    hc_app.status.update(
        {BSH_POWER_STATE: {ATTR_VALUE: "BSH.Common.EnumType.PowerState.Standby"}}
    )
    hc_app.status.update({BSH_ACTIVE_PROGRAM: {}})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "off")
    assert hass.states.is_state("switch.oven_program_hotair", "off")

    await hass.services.async_call(
        "switch", SERVICE_TOGGLE, {ATTR_ENTITY_ID: "switch.oven_power"}, blocking=True
    )
    await hass.services.async_call(
        "switch",
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.oven_program_hotair"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "on")
    assert hass.states.is_state("switch.oven_program_hotair", "on")

    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.oven_power"}, blocking=True
    )
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.oven_program_hotair"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "off")
    assert hass.states.is_state("switch.oven_program_hotair", "off")

    hc_app.status.update({BSH_POWER_STATE: {}})
    hc_app.status.update(
        {
            BSH_OPERATION_STATE: {
                ATTR_VALUE: "BSH.Common.EnumType.OperationState.Inactive"
            }
        }
    )

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "off")

    hc_app.status.update({BSH_OPERATION_STATE: {}})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.oven_power", "unknown")

    # Replace hc_app with a problematic appliance.
    hc_app = problematic_appliance

    hass.data[DOMAIN][config_entry.entry_id].devices[2]["device"].appliance = hc_app

    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.oven_power"}, blocking=True
    )
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.oven_program_hotair"},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.oven_power"}, blocking=True
    )
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.oven_program_hotair"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hc_app.set_setting.call_count == 2
    assert hc_app.start_program.call_count == 1
    assert hc_app.stop_program.call_count == 1
