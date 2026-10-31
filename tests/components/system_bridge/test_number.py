"""Tests for the System Bridge number platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.display_control import DisplayControl
from systembridgeconnector.models.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.response import Response

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

ENTITY_ID = "number.hostname_display_abc123_brightness"


@pytest.fixture(autouse=True)
def number_only() -> Generator[None]:
    """Enable only the number platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.NUMBER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_number_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the number platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_brightness_added_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test a brightness number is added once a display reports a brightness."""
    mock_websocket_client.listen.side_effect = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    display = replace(FIXTURE_DISPLAYS[0], id="def456", brightness=None)

    await coordinator.async_handle_module(Module.DISPLAYS, [*FIXTURE_DISPLAYS, display])
    await hass.async_block_till_done()

    assert hass.states.get("number.hostname_display_def456_brightness") is None

    await coordinator.async_handle_module(
        Module.DISPLAYS, [*FIXTURE_DISPLAYS, replace(display, brightness=25.0)]
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("number.hostname_display_def456_brightness"))
    assert state.state == "25.0"


@pytest.mark.usefixtures("init_integration")
async def test_brightness_display_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number is unavailable while its display is disconnected."""
    coordinator = mock_config_entry.runtime_data

    await coordinator.async_handle_module(Module.DISPLAYS, [])
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    await coordinator.async_handle_module(Module.DISPLAYS, FIXTURE_DISPLAYS)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "80.0"
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 1
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_brightness(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setting the brightness sends a display control."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: 50},
        blocking=True,
    )

    mock_websocket_client.display_control.assert_awaited_once_with(
        DisplayControl(id="abc123", brightness=50)
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_brightness_error(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test an error from System Bridge raises."""
    mock_websocket_client.display_control.return_value = Response(
        id=FIXTURE_REQUEST_ID,
        type=EventType.ERROR,
        message="Failed to set display brightness: not supported by this display",
        data={},
    )

    with pytest.raises(
        HomeAssistantError,
        match="Failed to control display abc123: Failed to set display brightness",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: 50},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_brightness_connection_closed(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test a closed connection raises."""
    mock_websocket_client.display_control.side_effect = ConnectionClosedException(
        "Connection is closed"
    )

    with pytest.raises(
        HomeAssistantError,
        match=r"A connection error occurred for TestSystem \(127\.0\.0\.1\)",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: 50},
            blocking=True,
        )
