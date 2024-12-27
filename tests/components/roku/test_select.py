"""Tests for the Roku select platform."""

from unittest.mock import MagicMock, patch

import pytest
from rokuecp import (
    Device as RokuDevice,
    RokuConnectionError,
    RokuConnectionTimeoutError,
    RokuError,
)
from syrupy import SnapshotAssertion

from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("mock_device", ["roku3", "rokutv-7820x"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the Roku select entities."""
    with patch("homeassistant.components.roku.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_application_select(
    hass: HomeAssistant,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the behavior of the Roku application select entity."""
    # application name
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_roku_3_application",
            ATTR_OPTION: "Netflix",
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with("12")

    # home
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_roku_3_application",
            ATTR_OPTION: "Home",
        },
        blocking=True,
    )

    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("home")


@pytest.mark.parametrize(
    ("error", "error_string"),
    [
        (RokuConnectionError, "Error communicating with Roku API"),
        (RokuConnectionTimeoutError, "Timeout communicating with Roku API"),
        (RokuError, "Invalid response from Roku API"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_application_select_error(
    hass: HomeAssistant,
    mock_roku: MagicMock,
    init_integration: MockConfigEntry,
    error: RokuError,
    error_string: str,
) -> None:
    """Test error handling of the Roku selects."""
    mock_roku.launch.side_effect = error

    with pytest.raises(HomeAssistantError, match=error_string):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.my_roku_3_application",
                ATTR_OPTION: "Netflix",
            },
            blocking=True,
        )

    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with("12")


@pytest.mark.parametrize("mock_device", ["rokutv-7820x"], indirect=True)
async def test_channel_select(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the behavior of the Roku channel select entity."""
    # channel name
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
            ATTR_OPTION: "WhatsOn (1.1)",
        },
        blocking=True,
    )

    assert mock_roku.tune.call_count == 1
    mock_roku.tune.assert_called_with("1.1")

    # channel number
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
            ATTR_OPTION: "99.1",
        },
        blocking=True,
    )

    assert mock_roku.tune.call_count == 2
    mock_roku.tune.assert_called_with("99.1")


@pytest.mark.parametrize("mock_device", ["rokutv-7820x"], indirect=True)
async def test_channel_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test error handling of the Roku selects."""
    mock_roku.tune.side_effect = RokuError

    with pytest.raises(HomeAssistantError, match="Invalid response from Roku API"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
                ATTR_OPTION: "99.1",
            },
            blocking=True,
        )

    # assert no state changes
    state = hass.states.get("select.58_onn_roku_tv_channel")
    assert state
    assert state.state == "getTV (14.3)"
    assert mock_roku.tune.call_count == 1
    mock_roku.tune.assert_called_with("99.1")
