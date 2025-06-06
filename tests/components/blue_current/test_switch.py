"""The tests for Bluecurrent switches."""

from homeassistant.components.blue_current import (
    CH_SETTINGS,
    CH_STATUS,
    PLUG_AND_CHARGE,
    Connector,
)
from homeassistant.components.blue_current.const import (
    ACTIVITY,
    BLOCK,
    PUBLIC_CHARGING,
    UNAVAILABLE,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import DEFAULT_CHARGE_POINT, DEFAULT_CHARGE_POINT_OPTIONS, init_integration

from tests.common import MockConfigEntry


async def test_switches(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the underlying switches."""

    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)

        assert state and state.state == STATE_OFF
        entry = entity_registry.async_get(switch.entity_id)
        assert entry and entry.unique_id == switch.unique_id


async def test_switches_offline(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if switches are disabled when needed."""
    charge_point = DEFAULT_CHARGE_POINT.copy()
    charge_point[ACTIVITY] = "offline"

    await init_integration(hass, config_entry, Platform.SWITCH, charge_point)

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)

        assert state and state.state == UNAVAILABLE
        entry = entity_registry.async_get(switch.entity_id)
        assert entry and entry.entity_id == switch.entity_id

    connector: Connector = config_entry.runtime_data
    connector.charge_points = {"101": {"activity": "charging"}}
    async_dispatcher_send(hass, "blue_current_charge_point_update_101")

    state = hass.states.get("switch.101_block_charge_point")
    assert state and state.state == UNAVAILABLE


async def test_toggle(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the on / off methods and if the switch gets updated."""
    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    connector: Connector = config_entry.runtime_data
    connector.charge_points = {
        "101": {"activity": "available", **DEFAULT_CHARGE_POINT_OPTIONS}
    }
    async_dispatcher_send(hass, "blue_current_charge_point_update_101")

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)

        assert state and state.state == STATE_OFF
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": switch.entity_id},
            blocking=True,
        )

        state = hass.states.get(switch.entity_id)
        assert state and state.state == STATE_ON

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": switch.entity_id},
            blocking=True,
        )

        state = hass.states.get(switch.entity_id)
        assert state and state.state == STATE_OFF


async def test_setting_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if the state of the switches are updated when an update message from the websocket comes in."""
    await init_integration(hass, config_entry, Platform.SWITCH)

    connector = config_entry.runtime_data

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)
        assert state.state == STATE_OFF

    connector.update_charge_point(
        "101",
        CH_SETTINGS,
        {
            PLUG_AND_CHARGE: True,
            PUBLIC_CHARGING: {"value": False, "permission": "write"},
        },
    )

    for switch in entity_entries:
        if switch.unique_id != f"{BLOCK}_101":
            switch = hass.states.get(switch.entity_id)
            assert switch.state == STATE_ON

    connector.update_charge_point("101", CH_STATUS, {ACTIVITY: UNAVAILABLE})

    for switch in entity_entries:
        if switch.unique_id != f"{BLOCK}_101":
            switch = hass.states.get(switch.entity_id)
            assert switch.state == STATE_UNAVAILABLE

    switch = hass.states.get("switch.101_block_charge_point")
    assert switch.state == STATE_ON
