"""Tests for the System Bridge switch platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.models.display_control import DisplayControl
from systembridgeconnector.models.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.modules.displays import DisplayPowerState
from systembridgeconnector.models.response import Response

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

ENTITY_ID = "switch.hostname_display_abc123_power"


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_switch_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the switch platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_display_power_added_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test a power switch is added once a display reports a power state."""
    mock_websocket_client.listen.side_effect = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    display = replace(FIXTURE_DISPLAYS[0], id="def456", power_state=None)

    await coordinator.async_handle_module(Module.DISPLAYS, [*FIXTURE_DISPLAYS, display])
    await hass.async_block_till_done()

    assert hass.states.get("switch.hostname_display_def456_power") is None

    await coordinator.async_handle_module(
        Module.DISPLAYS,
        [*FIXTURE_DISPLAYS, replace(display, power_state=DisplayPowerState.STANDBY)],
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.hostname_display_def456_power"))
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("service", "power_state"),
    [
        pytest.param(SERVICE_TURN_ON, DisplayPowerState.ON, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, DisplayPowerState.OFF, id="turn_off"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_display_power(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    service: str,
    power_state: DisplayPowerState,
) -> None:
    """Test turning the display on and off sends a display control."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_websocket_client.display_control.assert_awaited_once_with(
        DisplayControl(id="abc123", power_state=power_state)
    )


@pytest.mark.usefixtures("init_integration")
async def test_display_power_error(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test an error from System Bridge raises."""
    mock_websocket_client.display_control.return_value = Response(
        id=FIXTURE_REQUEST_ID,
        type=EventType.ERROR,
        message="Failed to set display power state: not supported by this display",
        data={},
    )

    with pytest.raises(
        HomeAssistantError,
        match="Failed to control display abc123: Failed to set display power state",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
