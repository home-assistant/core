"""Test squeezebox initialization."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.squeezebox import async_remove_config_entry_device
from homeassistant.components.squeezebox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceRegistry

from .conftest import TEST_MAC

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def squeezebox_media_player_platform():
    """Only set up the media_player platform for squeezebox tests."""
    with patch(
        "homeassistant.components.squeezebox.PLATFORMS", [Platform.MEDIA_PLAYER]
    ):
        yield


@pytest.fixture(autouse=True)
def mock_discovery():
    """Mock discovery of squeezebox players."""
    with patch("homeassistant.components.squeezebox.media_player.async_discover"):
        yield


async def test_init_api_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to API fail."""

    # Setup component to fail...
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_init_timeout_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to TimeoutError."""

    # Setup component to raise TimeoutError
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            side_effect=TimeoutError,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_unauthorized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to unauthorized error."""

    # Setup component to simulate unauthorized response
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,  # async_query returns False on auth failure
        ),
        patch(
            "homeassistant.components.squeezebox.Server",  # Patch the Server class itself
            autospec=True,
        ) as mock_server_instance,
    ):
        mock_server_instance.return_value.http_status = HTTPStatus.UNAUTHORIZED
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_init_missing_uuid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to missing UUID in server status."""
    # A response that is truthy but does not contain STATUS_QUERY_UUID
    mock_status_without_uuid = {"name": "Test Server"}

    with patch(
        "homeassistant.components.squeezebox.Server.async_query",
        return_value=mock_status_without_uuid,
    ) as mock_async_query:
        # ConfigEntryError is raised, caught by setup, and returns False
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        mock_async_query.assert_called_once_with(
            "serverstatus", "-", "-", "prefs:libraryname"
        )


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    configured_player: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test squeezebox device registered in the device registry."""
    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_MAC[0])})
    assert reg_device is not None
    assert reg_device == snapshot


async def test_device_registry_server_merged(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    configured_players: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test squeezebox device registered in the device registry."""
    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_MAC[2])})
    assert reg_device is not None
    assert reg_device == snapshot


@pytest.mark.parametrize(
    ("is_service", "is_online", "expected_error"),
    [
        (True, False, "Please delete the associated config entry"),
        (False, True, "is currently online"),
    ],
)
async def test_remove_device_blocked(
    hass: HomeAssistant,
    setup_squeezebox: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    is_service: bool,
    is_online: bool,
    expected_error: str,
) -> None:
    """Test that removal is blocked for server or online players."""
    entry = setup_squeezebox
    device: dr.DeviceEntry | None

    if is_service:
        device = next(
            d
            for d in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
            if d.entry_type is dr.DeviceEntryType.SERVICE
        )
    else:
        player_id = TEST_MAC[0]
        entry.runtime_data.player_coordinators[player_id].available = is_online
        device = device_registry.async_get_device(identifiers={(DOMAIN, player_id)})

    assert device is not None
    with pytest.raises(HomeAssistantError, match=expected_error):
        await async_remove_config_entry_device(hass, entry, device)
