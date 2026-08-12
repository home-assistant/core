"""Tests for the Sonos button platform."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from sonos_websocket import CLIP_ID_KEY
from sonos_websocket.exception import SonosWebsocketError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

CANCEL_ANNOUNCEMENT_BUTTON = "button.zone_a_cancel_announcement"


async def _announce_clip(hass: HomeAssistant, content_id: str) -> None:
    """Play an announcement clip to set the active clip id."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.zone_a",
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_CONTENT_ID: content_id,
            ATTR_MEDIA_ANNOUNCE: True,
        },
        blocking=True,
    )


async def test_cancel_announcement_no_prior(
    hass: HomeAssistant,
    async_autosetup_sonos,
) -> None:
    """Test cancelling when no announcement has been played."""
    with pytest.raises(
        ServiceValidationError, match="No active announcement to cancel"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: CANCEL_ANNOUNCEMENT_BUTTON},
            blocking=True,
        )


async def test_cancel_announcement(
    hass: HomeAssistant,
    async_autosetup_sonos,
    sonos_websocket,
) -> None:
    """Test cancelling a currently playing announcement."""
    content_id = "http://10.0.0.1:8123/local/sounds/doorbell.mp3"
    sonos_websocket.play_clip.return_value = [
        {"success": 1},
        {CLIP_ID_KEY: "clip-123"},
    ]
    await _announce_clip(hass, content_id)

    sonos_websocket.cancel_clip = AsyncMock(return_value=[{"success": 1}, {}])
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: CANCEL_ANNOUNCEMENT_BUTTON},
        blocking=True,
    )
    sonos_websocket.cancel_clip.assert_called_once_with("clip-123")


async def test_cancel_announcement_no_clip_id_from_announce_response(
    hass: HomeAssistant,
    async_autosetup_sonos,
    sonos_websocket,
) -> None:
    """Test cancelling fails when the announce response has no clip ID."""
    content_id = "http://10.0.0.1:8123/local/sounds/doorbell.mp3"
    sonos_websocket.play_clip.return_value = [{"success": 1}, None]
    await _announce_clip(hass, content_id)

    with pytest.raises(
        ServiceValidationError, match="No active announcement to cancel"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: CANCEL_ANNOUNCEMENT_BUTTON},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("cancel_clip_side_effect", "cancel_clip_return", "error_match"),
    [
        pytest.param(
            SonosWebsocketError("Connection lost"),
            None,
            "Failed to reach Sonos speaker for announcement: Connection lost",
            id="websocket_error",
        ),
        pytest.param(
            None,
            [{"success": 0}, {}],
            "Cancelling announcement failed",
            id="non_success_response",
        ),
    ],
)
async def test_cancel_announcement_errors(
    hass: HomeAssistant,
    async_autosetup_sonos,
    sonos_websocket,
    cancel_clip_side_effect: SonosWebsocketError | None,
    cancel_clip_return: list[dict[str, Any]] | None,
    error_match: str,
) -> None:
    """Test error handling when cancelling an announcement."""
    content_id = "http://10.0.0.1:8123/local/sounds/doorbell.mp3"
    sonos_websocket.play_clip.return_value = [
        {"success": 1},
        {CLIP_ID_KEY: "clip-123"},
    ]
    await _announce_clip(hass, content_id)

    sonos_websocket.cancel_clip = AsyncMock(
        side_effect=cancel_clip_side_effect,
        return_value=cancel_clip_return,
    )
    with pytest.raises(HomeAssistantError, match=error_match):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: CANCEL_ANNOUNCEMENT_BUTTON},
            blocking=True,
        )
