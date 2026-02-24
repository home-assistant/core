"""Tests for ZoneMinder switch entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol
from zoneminder.monitor import MonitorState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.components.zoneminder.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import create_mock_monitor

from tests.common import async_fire_time_changed


async def _setup_zm_with_switches(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    zm_config: dict,
    monitors: list,
    freezer: FrozenDateTimeFactory,
    command_on: str = "Modect",
    command_off: str = "Monitor",
) -> None:
    """Set up ZM component with switch platform and trigger first poll."""
    mock_zoneminder_client.get_monitors.return_value = monitors

    assert await async_setup_component(hass, DOMAIN, zm_config)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: [
                {
                    "platform": DOMAIN,
                    "command_on": command_on,
                    "command_off": command_off,
                }
            ]
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    # Trigger first poll to update entity state
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_switch_per_monitor(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    two_monitors: list,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one switch entity is created per monitor."""
    await _setup_zm_with_switches(
        hass, mock_zoneminder_client, single_server_config, two_monitors, freezer
    )

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 2


async def test_switch_name_format(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch name format is '{name} State'."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_switches(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.name == "Front Door State"


async def test_switch_on_when_function_matches_command_on(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch is ON when monitor function matches command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_switches(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        command_on="Modect",
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_off_when_function_differs(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch is OFF when monitor function differs from command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await _setup_zm_with_switches(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        command_on="Modect",
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_on_service(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turn_on service sets monitor function to command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await _setup_zm_with_switches(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify monitor function was set to MonitorState("Modect")
    assert monitors[0].function == MonitorState("Modect")


async def test_switch_turn_off_service(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turn_off service sets monitor function to command_off."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_switches(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].function == MonitorState("Monitor")


async def test_switch_icon(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch icon is mdi:record-rec."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_switches(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:record-rec"


async def test_switch_platform_not_ready_empty_monitors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test PlatformNotReady on empty monitors."""
    mock_zoneminder_client.get_monitors.return_value = []

    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()
    await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: [
                {
                    "platform": DOMAIN,
                    "command_on": "Modect",
                    "command_off": "Monitor",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 0


def test_platform_schema_requires_command_on_off() -> None:
    """Test platform schema requires command_on and command_off."""
    # Missing command_on
    with pytest.raises(vol.MultipleInvalid):
        PLATFORM_SCHEMA({"platform": "zoneminder", "command_off": "Monitor"})

    # Missing command_off
    with pytest.raises(vol.MultipleInvalid):
        PLATFORM_SCHEMA({"platform": "zoneminder", "command_on": "Modect"})
