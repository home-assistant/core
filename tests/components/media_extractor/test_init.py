"""The tests for Media Extractor integration."""
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.media_extractor import DOMAIN
from homeassistant.components.media_player import SERVICE_PLAY_MEDIA
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components.media_extractor import MockYoutubeDL


async def test_play_media_service_is_registered(hass: HomeAssistant) -> None:
    """Test play media service is registered."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_PLAY_MEDIA)


@pytest.mark.parametrize(
    "config_fixture", ["empty_media_extractor_config", "audio_media_extractor_config"]
)
@pytest.mark.parametrize(
    ("media_content_id", "media_content_type"),
    [("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "VIDEO")],
)
async def test_play_media_service(
    hass: HomeAssistant,
    mock_youtube_dl: MockYoutubeDL,
    calls: list[ServiceCall],
    snapshot: SnapshotAssertion,
    request: pytest.FixtureRequest,
    config_fixture: str,
    media_content_id: str,
    media_content_type: str,
) -> None:
    """Test play media service is registered."""
    config: dict[str, Any] = request.getfixturevalue(config_fixture)
    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            "entity_id": "media_player.bedroom",
            "media_content_type": media_content_type,
            "media_content_id": media_content_id,
        },
    )
    await hass.async_block_till_done()

    assert calls[0].data == snapshot


async def test_download_error(
    hass: HomeAssistant,
    empty_media_extractor_config: dict[str, Any],
    calls: list[ServiceCall],
) -> None:
    """Test handling DownloadError."""

    await async_setup_component(hass, DOMAIN, empty_media_extractor_config)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.media_extractor.YoutubeDL", return_value="yes"
    ):
        # mock.return_value.extract_info.side_effect = DownloadError

        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                "entity_id": "media_player.bedroom",
                "media_content_type": "VIDEO",
                "media_content_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            },
        )

    assert len(calls) == 0
