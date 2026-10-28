"""Tests for the System Bridge switch platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.models.display_control import DisplayControl
from systembridgeconnector.models.modules.displays import DisplayPowerState
from systembridgeconnector.models.response import Response

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
