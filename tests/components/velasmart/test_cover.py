"""Tests for the VelaSmart cover platform."""

from unittest.mock import AsyncMock, patch

from velasmart import VelaSmartApiClient

from homeassistant.components.velasmart.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE = {
    "id": "device1",
    "name": "Living Room Curtain",
    "gateway_mac": "aa:bb:cc:dd:ee:ff",
    "device_type": 3,
    "position": 50,
    "is_closed": False,
    "online": True,
    "battery": 100,
}


async def _setup_entry(hass: HomeAssistant) -> None:
    """Set up a config entry with a single mocked device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_cover_entities_created(hass: HomeAssistant) -> None:
    """Test that cover entities are created from coordinator data."""
    with patch.object(
        VelaSmartApiClient, "get_devices", new_callable=AsyncMock, return_value=[DEVICE]
    ):
        await _setup_entry(hass)

    state = hass.states.get("cover.living_room_curtain")
    assert state is not None
    assert state.state == "open"
    assert state.attributes["current_position"] == 50


async def test_open_cover(hass: HomeAssistant) -> None:
    """Test opening a curtain sends the correct command."""
    with (
        patch.object(
            VelaSmartApiClient,
            "get_devices",
            new_callable=AsyncMock,
            return_value=[DEVICE],
        ),
        patch.object(
            VelaSmartApiClient, "send_command", new_callable=AsyncMock
        ) as mock_send,
    ):
        await _setup_entry(hass)
        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": "cover.living_room_curtain"},
            blocking=True,
        )
        mock_send.assert_called_once_with("device1", 3, 100)


async def test_close_cover(hass: HomeAssistant) -> None:
    """Test closing a curtain sends the correct command."""
    with (
        patch.object(
            VelaSmartApiClient,
            "get_devices",
            new_callable=AsyncMock,
            return_value=[DEVICE],
        ),
        patch.object(
            VelaSmartApiClient, "send_command", new_callable=AsyncMock
        ) as mock_send,
    ):
        await _setup_entry(hass)
        await hass.services.async_call(
            "cover",
            "close_cover",
            {"entity_id": "cover.living_room_curtain"},
            blocking=True,
        )
        mock_send.assert_called_once_with("device1", 3, 0)


async def test_set_cover_position(hass: HomeAssistant) -> None:
    """Test setting the position sends the correct command."""
    with (
        patch.object(
            VelaSmartApiClient,
            "get_devices",
            new_callable=AsyncMock,
            return_value=[DEVICE],
        ),
        patch.object(
            VelaSmartApiClient, "send_command", new_callable=AsyncMock
        ) as mock_send,
    ):
        await _setup_entry(hass)
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": "cover.living_room_curtain", "position": 75},
            blocking=True,
        )
        mock_send.assert_called_once_with("device1", 3, 75)
