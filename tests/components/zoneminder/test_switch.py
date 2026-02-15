"""Tests for ZoneMinder switch entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from zoneminder.monitor import Monitor, MonitorState

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
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import create_mock_monitor, create_mock_zm_client

from tests.common import async_fire_time_changed


async def _setup_zm_with_switches(
    hass: HomeAssistant,
    zm_config: dict,
    monitors: list,
    command_on: str = "Modect",
    command_off: str = "Monitor",
) -> MagicMock:
    """Set up ZM component with switch platform and trigger first poll."""
    client = create_mock_zm_client(monitors=monitors)

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
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
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    return client


async def test_switch_per_monitor(
    hass: HomeAssistant, single_server_config, two_monitors
) -> None:
    """Test one switch entity is created per monitor."""
    await _setup_zm_with_switches(hass, single_server_config, two_monitors)

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 2


async def test_switch_name_format(hass: HomeAssistant, single_server_config) -> None:
    """Test switch name format is '{name} State'."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_switches(hass, single_server_config, monitors)

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.name == "Front Door State"


async def test_switch_on_when_function_matches_command_on(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test switch is ON when monitor function matches command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_switches(
        hass, single_server_config, monitors, command_on="Modect"
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_off_when_function_differs(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test switch is OFF when monitor function differs from command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await _setup_zm_with_switches(
        hass, single_server_config, monitors, command_on="Modect"
    )

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_on_service(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test turn_on service sets monitor function to command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await _setup_zm_with_switches(hass, single_server_config, monitors)

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
    hass: HomeAssistant, single_server_config
) -> None:
    """Test turn_off service sets monitor function to command_off."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_switches(hass, single_server_config, monitors)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].function == MonitorState("Monitor")


async def test_switch_icon(hass: HomeAssistant, single_server_config) -> None:
    """Test switch icon is mdi:record-rec."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_switches(hass, single_server_config, monitors)

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:record-rec"


async def test_switch_platform_not_ready_empty_monitors(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test PlatformNotReady on empty monitors."""
    client = create_mock_zm_client(monitors=[])

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
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


@pytest.mark.xfail(reason="BUG-05: No unique_id on any entity")
async def test_switch_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, single_server_config
) -> None:
    """Switch entities should have unique_id for UI customization.

    No entity in the integration sets unique_id. This means entities cannot
    be customized via the HA UI and are fragile to name changes.
    """
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_switches(hass, single_server_config, monitors)

    entry = entity_registry.async_get("switch.front_door_state")
    assert entry is not None
    assert entry.unique_id is not None


@pytest.mark.xfail(
    reason="BUG-03: monitor.function getter makes HTTP call on every read"
)
async def test_function_read_no_side_effects(
    hass: HomeAssistant, single_server_config
) -> None:
    """Reading monitor.function should not trigger an HTTP request.

    The zm-py Monitor.function property calls update_monitor() on every read,
    which makes an HTTP GET to monitors/{id}.json. The switch platform reads
    function to determine on/off state, triggering unnecessary API traffic.
    """
    stub_client = MagicMock()
    stub_client.get_state.return_value = {
        "monitor": {
            "Monitor": {"Function": "Modect"},
            "Monitor_Status": {"CaptureFPS": "15.00"},
        }
    }
    stub_client.verify_ssl = True

    raw_result = {
        "Monitor": {
            "Id": "1",
            "Name": "Test",
            "Controllable": "0",
            "StreamReplayBuffer": "0",
            "ServerId": "0",
        },
        "Monitor_Status": {"CaptureFPS": "15.00"},
    }
    stub_client.get_zms_url_for_monitor.return_value = "http://example.com/zms"
    stub_client.get_url_with_auth.return_value = "http://example.com/zms?auth=1"

    monitor = Monitor(stub_client, raw_result)
    stub_client.get_state.reset_mock()

    # Reading function should NOT make an HTTP call
    _ = monitor.function
    assert stub_client.get_state.call_count == 0
