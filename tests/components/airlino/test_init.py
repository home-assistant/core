"""Tests for AirLino config-entry lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import AirlinoApiConnectionError
import pytest

from homeassistant.components.airlino import AirlinoRuntimeData
from homeassistant.components.airlino.const import CONF_SETUP_VERIFIED, DOMAIN
from homeassistant.components.airlino.coordinator import AirlinoDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api() -> MagicMock:
    """Create a mocked API client with successful update responses."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        return_value={"devicename": "Living room", "model": "AirLino"}
    )
    api.async_get_player_status = AsyncMock(return_value={"state": 1})
    api.async_get_master_volume = AsyncMock(return_value=50)
    api.async_get_sender_status = AsyncMock(
        return_value={"enabled": False, "uuid": "sender-uuid"}
    )
    api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
    api.async_close = AsyncMock()
    return api


async def test_setup_verifies_entry_and_starts_platform(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Persist setup verification only after the first successful refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: False},
        unique_id="00:11:22:33:44:55",
    )
    entry.add_to_hass(hass)
    forward_setups = AsyncMock()

    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", forward_setups),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.data[CONF_SETUP_VERIFIED] is True
    assert isinstance(entry.runtime_data, AirlinoRuntimeData)
    assert isinstance(entry.runtime_data.coordinator, AirlinoDataUpdateCoordinator)
    forward_setups.assert_awaited_once()


async def test_verified_entry_loads_unavailable_when_device_is_offline(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Load a previously verified entry even while its device is offline."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: True},
        unique_id="00:11:22:33:44:55",
    )
    entry.add_to_hass(hass)
    mock_api.async_get_device_info.side_effect = AirlinoApiConnectionError("offline")
    forward_setups = AsyncMock()

    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", forward_setups),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data.coordinator.data["online"] is False
    forward_setups.assert_awaited_once()


async def test_setup_defers_unverified_entry_when_device_is_unreachable(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Do not mark a new entry verified if its initial refresh fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: False},
        unique_id="00:11:22:33:44:55",
    )
    entry.add_to_hass(hass)
    mock_api.async_get_device_info.side_effect = AirlinoApiConnectionError("offline")

    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.data[CONF_SETUP_VERIFIED] is False
    mock_api.async_close.assert_not_awaited()


async def test_unload_closes_api_when_platform_unloads(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Close the API session after its platform has unloaded successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: False},
    )
    entry.add_to_hass(hass)
    forward_setups = AsyncMock()
    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", forward_setups),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    unload_platforms = AsyncMock(return_value=True)
    with patch.object(hass.config_entries, "async_unload_platforms", unload_platforms):
        assert await hass.config_entries.async_unload(entry.entry_id)

    mock_api.async_close.assert_awaited_once()


async def test_unload_keeps_api_open_when_platform_unload_fails(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Keep the API client open if Home Assistant could not unload the platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: False},
    )
    entry.add_to_hass(hass)
    forward_setups = AsyncMock()
    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", forward_setups),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    unload_platforms = AsyncMock(return_value=False)
    with patch.object(hass.config_entries, "async_unload_platforms", unload_platforms):
        assert not await hass.config_entries.async_unload(entry.entry_id)

    mock_api.async_close.assert_not_awaited()
