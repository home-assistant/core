"""Tests for the System Bridge select platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.system_control import PowerProfileRequest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

ENTITY_ID = "select.hostname_power_profile"


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.SELECT],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_select_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the select platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_power_profile(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test picking a power profile switches to it."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "performance"},
        blocking=True,
    )

    mock_websocket_client.set_power_profile.assert_awaited_once_with(
        PowerProfileRequest(profile="performance")
    )


@pytest.mark.usefixtures("mock_version")
async def test_power_profile_added_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the select is added once the system reports a power profile."""
    modules_data = mock_websocket_client.get_data.return_value
    system = modules_data.system
    mock_websocket_client.get_data.return_value = replace(
        modules_data, system=replace(system, power_profile=None, power_profiles=[])
    )
    mock_websocket_client.listen.side_effect = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_handle_module(Module.SYSTEM, system)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "balanced"

    await coordinator.async_handle_module(
        Module.SYSTEM, replace(system, power_profile=None)
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("response", "message"),
    [
        pytest.param(
            Response(
                id=FIXTURE_REQUEST_ID,
                type=EventType.ERROR,
                message="power-profiles-daemon is not running",
                data={},
            ),
            "System Bridge couldn't make the change: power-profiles-daemon is not running",
            id="error",
        ),
        pytest.param(
            ConnectionClosedException,
            "A connection error occurred",
            id="connection_closed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_profile_error(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    response: Response | type[Exception],
    message: str,
) -> None:
    """Test a failed switch raises."""
    mock_websocket_client.set_power_profile.side_effect = [response]

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "performance"},
            blocking=True,
        )
