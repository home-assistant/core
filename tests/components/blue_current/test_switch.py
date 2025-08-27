"""The tests for Bluecurrent switches."""

from homeassistant.components.blue_current import CHARGEPOINT_SETTINGS, PLUG_AND_CHARGE
from homeassistant.components.blue_current.const import (
    ACTIVITY,
    CHARGEPOINT_STATUS,
    PUBLIC_CHARGING,
    UNAVAILABLE,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from . import DEFAULT_CHARGE_POINT, init_integration

from tests.common import MockConfigEntry


async def test_switches(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: EntityRegistry
) -> None:
    """Test the underlying switches."""

    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)

        assert state and state.state == STATE_OFF
        entry = entity_registry.async_get(switch.entity_id)
        assert entry and entry.unique_id == switch.unique_id


async def test_switches_offline(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: EntityRegistry
) -> None:
    """Test if switches are disabled when needed."""
    charge_point = DEFAULT_CHARGE_POINT.copy()
    charge_point[ACTIVITY] = "offline"

    await init_integration(hass, config_entry, Platform.SWITCH, charge_point)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)

        assert state and state.state == UNAVAILABLE
        entry = entity_registry.async_get(switch.entity_id)
        assert entry and entry.entity_id == switch.entity_id


async def test_block_switch_availability(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: EntityRegistry
) -> None:
    """Test if the block switch is unavailable when charging."""
    charge_point = DEFAULT_CHARGE_POINT.copy()
    charge_point[ACTIVITY] = "charging"

    await init_integration(hass, config_entry, Platform.SWITCH, charge_point)

    state = hass.states.get("switch.101_block_charge_point")
    assert state and state.state == UNAVAILABLE


async def test_toggle(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: EntityRegistry
) -> None:
    """Test the on / off methods and if the switch gets updated."""
    await init_integration(hass, config_entry, Platform.SWITCH)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

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
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: EntityRegistry
) -> None:
    """Test if the state of the switches are updated when an update message from the websocket comes in."""
    integration = await init_integration(hass, config_entry, Platform.SWITCH)
    client_mock = integration[0]

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for switch in entity_entries:
        state = hass.states.get(switch.entity_id)
        assert state.state == STATE_OFF

    await client_mock.update_charge_point(
        "101",
        CHARGEPOINT_SETTINGS,
        {
            PLUG_AND_CHARGE: True,
            PUBLIC_CHARGING: {"value": False, "permission": "write"},
        },
    )

    charge_cards_only_switch = hass.states.get("switch.101_linked_charging_cards_only")
    assert charge_cards_only_switch.state == STATE_ON

    plug_and_charge_switch = hass.states.get("switch.101_plug_charge")
    assert plug_and_charge_switch.state == STATE_ON

    plug_and_charge_switch = hass.states.get("switch.101_block_charge_point")
    assert plug_and_charge_switch.state == STATE_OFF

    await client_mock.update_charge_point(
        "101", CHARGEPOINT_STATUS, {ACTIVITY: UNAVAILABLE}
    )

    charge_cards_only_switch = hass.states.get("switch.101_linked_charging_cards_only")
    assert charge_cards_only_switch.state == STATE_UNAVAILABLE

    plug_and_charge_switch = hass.states.get("switch.101_plug_charge")
    assert plug_and_charge_switch.state == STATE_UNAVAILABLE

    switch = hass.states.get("switch.101_block_charge_point")
    assert switch.state == STATE_ON
