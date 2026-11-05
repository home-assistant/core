"""Tests for ZoneMinder switch entities."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from zoneminder.monitor import MonitorState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_CONFIG_DATA, MOCK_OPTIONS, create_mock_monitor

ENTITY_ID = "switch.front_door_state"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an entity update poll."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one switch entity is created per monitor."""
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await _poll(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_follows_server_change(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the switch is unknown without a function, then follows the server."""
    monitor = create_mock_monitor(function=None)
    mock_zoneminder_client.get_monitors.return_value = [monitor]
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await _poll(hass, freezer)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    def change_on_server() -> None:
        monitor.function = MonitorState.MODECT

    # zm-py only fetches new monitor data in update_monitor
    monitor.update_monitor.side_effect = change_on_server
    await _poll(hass, freezer)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("options", "service", "expected"),
    [
        pytest.param(MOCK_OPTIONS, SERVICE_TURN_ON, MonitorState.MODECT, id="on"),
        pytest.param(MOCK_OPTIONS, SERVICE_TURN_OFF, MonitorState.MONITOR, id="off"),
        pytest.param(
            {**MOCK_OPTIONS, CONF_COMMAND_ON: "record"},
            SERVICE_TURN_ON,
            MonitorState.RECORD,
            id="custom_on",
        ),
        pytest.param(
            {**MOCK_OPTIONS, CONF_COMMAND_OFF: "none"},
            SERVICE_TURN_OFF,
            MonitorState.NONE,
            id="custom_off",
        ),
    ],
)
async def test_switch_services(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    options: dict[str, Any],
    service: str,
    expected: MonitorState,
) -> None:
    """Test turning the switch on and off sets the configured monitor function."""
    monitor = create_mock_monitor(function=None)
    mock_zoneminder_client.get_monitors.return_value = [monitor]
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA, options=options)
    await setup_integration(hass, entry, [Platform.SWITCH])

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert monitor.function == expected


async def test_switch_off_when_function_differs(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the switch is off when the monitor function is not command_on."""
    mock_zoneminder_client.get_monitors.return_value = [
        create_mock_monitor(function=MonitorState.RECORD)
    ]
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await _poll(hass, freezer)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
