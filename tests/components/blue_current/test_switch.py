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
    LINKED_CHARGE_CARDS,
    PUBLIC_CHARGING,
    UNAVAILABLE,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import DEFAULT_CHARGE_POINT, DEFAULT_CHARGE_POINT_OPTIONS, init_integration

from tests.common import MockConfigEntry

SWITCHES = [PLUG_AND_CHARGE, BLOCK, LINKED_CHARGE_CARDS]


async def test_switches(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the underlying switches."""

    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_registry = er.async_get(hass)

    for key in SWITCHES:
        state = hass.states.get(f"switch.101_{key}")

        assert state and state.state == STATE_OFF
        entry = entity_registry.async_get(f"switch.101_{key}")
        assert entry and entry.unique_id == f"{key}_101"

    state = hass.states.get("switch.101_block")
    assert state and state.state == STATE_OFF
    entry = entity_registry.async_get("switch.101_block")
    assert entry and entry.unique_id == "block_101"


async def test_switches_offline(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if switches are disabled when needed."""
    charge_point = DEFAULT_CHARGE_POINT.copy()
    charge_point[ACTIVITY] = "offline"

    await init_integration(hass, config_entry, Platform.SWITCH, charge_point)

    entity_registry = er.async_get(hass)

    for key in SWITCHES:
        state = hass.states.get(f"switch.101_{key}")

        assert state and state.state == UNAVAILABLE
        entry = entity_registry.async_get(f"switch.101_{key}")
        assert entry and entry.unique_id == f"{key}_101"

    connector: Connector = config_entry.runtime_data
    connector.charge_points = {"101": {"activity": "charging"}}
    async_dispatcher_send(hass, "blue_current_charge_point_update_101")

    state = hass.states.get("switch.101_block")
    assert state and state.state == UNAVAILABLE


async def test_toggle(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the on / off methods and if the switch gets updated."""
    await init_integration(hass, config_entry, Platform.SWITCH)

    connector: Connector = config_entry.runtime_data
    connector.charge_points = {
        "101": {"activity": "available", **DEFAULT_CHARGE_POINT_OPTIONS}
    }
    async_dispatcher_send(hass, "blue_current_charge_point_update_101")

    for switch in SWITCHES:
        state = hass.states.get(f"switch.101_{switch}")

        assert state and state.state == STATE_OFF
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": f"switch.101_{switch}"},
            blocking=True,
        )

        state = hass.states.get(f"switch.101_{switch}")
        assert state and state.state == STATE_ON

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": f"switch.101_{switch}"},
            blocking=True,
        )

        state = hass.states.get(f"switch.101_{switch}")
        assert state and state.state == STATE_OFF


async def test_setting_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if the state of the switches are updated when an update message from the websocket comes in."""
    await init_integration(hass, config_entry, Platform.SWITCH)

    connector = config_entry.runtime_data

    for key in (PLUG_AND_CHARGE, LINKED_CHARGE_CARDS, BLOCK):
        switch = hass.states.get(f"switch.101_{key}")
        assert switch.state == STATE_OFF

    connector.update_charge_point(
        "101",
        CH_SETTINGS,
        {
            PLUG_AND_CHARGE: True,
            PUBLIC_CHARGING: {"value": False, "permission": "write"},
        },
    )

    for key in (PLUG_AND_CHARGE, LINKED_CHARGE_CARDS):
        switch = hass.states.get(f"switch.101_{key}")
        assert switch.state == STATE_ON

    connector.update_charge_point("101", CH_STATUS, {ACTIVITY: UNAVAILABLE})

    for key in (PLUG_AND_CHARGE, LINKED_CHARGE_CARDS):
        switch = hass.states.get(f"switch.101_{key}")
        assert switch.state == STATE_UNAVAILABLE

    switch = hass.states.get("switch.101_block")
    assert switch.state == STATE_ON
