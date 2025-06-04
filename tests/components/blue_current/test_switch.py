"""The tests for Bluecurrent switches."""

from homeassistant.components.blue_current import PLUG_AND_CHARGE, VALUE, Connector
from homeassistant.components.blue_current.const import (
    ACTIVITY,
    BLOCK,
    PUBLIC_CHARGING,
    UNAVAILABLE,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import DEFAULT_CHARGE_POINT, DEFAULT_CHARGE_POINT_OPTIONS, init_integration

from tests.common import MockConfigEntry


async def test_switches(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the underlying switches."""

    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_registry = er.async_get(hass)

    for key, data_object in DEFAULT_CHARGE_POINT_OPTIONS.items():
        state = hass.states.get(f"switch.101_{key}")

        if data_object[VALUE]:
            check = STATE_ON
        else:
            check = STATE_OFF
        assert state and state.state == check
        entry = entity_registry.async_get(f"switch.101_{key}")
        assert entry and entry.unique_id == f"{key}_101"

    # block
    switches = er.async_entries_for_config_entry(entity_registry, "uuid")
    assert len(DEFAULT_CHARGE_POINT_OPTIONS.keys()) == len(switches) - 1

    state = hass.states.get("switch.101_block")
    assert state and state.state == STATE_OFF
    entry = entity_registry.async_get("switch.101_block")
    assert entry and entry.unique_id == "block_101"


async def test_switches_unavailable(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if switches are disabled when needed."""
    DEFAULT_CHARGE_POINT[ACTIVITY] = UNAVAILABLE

    await init_integration(hass, config_entry, Platform.SWITCH, DEFAULT_CHARGE_POINT)

    entity_registry = er.async_get(hass)

    for key in DEFAULT_CHARGE_POINT_OPTIONS:
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
    DEFAULT_CHARGE_POINT[PUBLIC_CHARGING][VALUE] = False

    await init_integration(hass, config_entry, Platform.SWITCH)

    connector: Connector = config_entry.runtime_data
    connector.charge_points = {
        "101": {"activity": "available", **DEFAULT_CHARGE_POINT_OPTIONS}
    }
    async_dispatcher_send(hass, "blue_current_charge_point_update_101")

    switches = [PUBLIC_CHARGING, BLOCK, PLUG_AND_CHARGE]

    for switch in switches:
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
