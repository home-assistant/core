"""Test the Discord notify entity."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest

from homeassistant.components.discord.const import DOMAIN
from homeassistant.components.discord.notify import DiscordNotifyEntity
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import CHANNEL_NAME

# The entity_id is generated from the bot title + channel name.
# With has_entity_name=True: "Mock Discord Bot General"  → notify.mock_discord_bot_general
ENTITY_ID = f"notify.mock_discord_bot_{CHANNEL_NAME}"


async def test_send_message(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test sending a basic text message to a Discord channel."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "Hello Discord!",
        },
        blocking=True,
    )

    mock_channel.send.assert_called_once_with("Hello Discord!")


async def test_send_message_with_title(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that a title is prepended in bold to the message."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "Alert",
        },
        blocking=True,
    )

    mock_channel.send.assert_called_once_with("**Alert**\nHello")


async def test_send_message_channel_not_found(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
) -> None:
    """Test that a HomeAssistantError is raised when the channel is not found."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "test"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "channel_not_found"


async def test_send_message_falls_back_to_dm(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that an unknown channel ID falls back to a DM user lookup."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(return_value=mock_channel)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "DM!"},
        blocking=True,
    )

    mock_channel.send.assert_called_once()


async def test_send_message_http_error_raises(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that an HTTP error during send raises HomeAssistantError."""
    mock_channel.send = AsyncMock(
        side_effect=nextcord.HTTPException(MagicMock(), "rate limited")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "oops"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "send_message_failed"


async def test_service_send_message_text_only(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test discord.send_message service with message only sends with empty files and embeds."""
    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {ATTR_ENTITY_ID: ENTITY_ID, "message": "Hello"},
        blocking=True,
    )
    mock_channel.send.assert_called_once_with("Hello", files=[], embeds=[])


async def test_service_send_message_with_title(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test discord.send_message with title prepends bold text."""
    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {ATTR_ENTITY_ID: ENTITY_ID, "message": "Hello", "title": "Alert"},
        blocking=True,
    )
    mock_channel.send.assert_called_once_with("**Alert**\nHello", files=[], embeds=[])


async def test_service_send_image_local_file(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that a valid local file path is attached as a nextcord.File."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"fake-image-data")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    with patch("homeassistant.components.discord.notify.nextcord.File") as mock_file:
        mock_file.return_value = MagicMock()
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {ATTR_ENTITY_ID: ENTITY_ID, "message": "img", "images": [str(img)]},
            blocking=True,
        )
    mock_file.assert_called_once_with(str(img), "test.jpg")
    assert mock_channel.send.call_args[1]["files"]


async def test_service_send_image_path_not_allowed(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
) -> None:
    """Test that a path outside the allowlist raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "img",
                "images": ["/not/allowed/file.jpg"],
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "path_not_allowed"


async def test_service_send_image_file_not_found(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that an allowed but missing file raises HomeAssistantError."""
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "img",
                "images": [str(tmp_path / "missing.jpg")],
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "file_not_found"


async def test_service_send_url_attachment(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that a URL in the allowlist is downloaded and attached."""
    hass.config.allowlist_external_urls = {"https://example.com/"}
    fake_bytes = bytearray(b"fake-image-bytes")

    with patch.object(
        DiscordNotifyEntity,
        "async_get_file_from_url",
        AsyncMock(return_value=fake_bytes),
    ):
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "url",
                "urls": ["https://example.com/img.png"],
            },
            blocking=True,
        )
    assert mock_channel.send.call_args[1]["files"]


async def test_service_send_url_not_allowed(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that a URL not in the allowlist is skipped without error."""
    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "message": "url",
            "urls": ["https://blocked.example.com/img.png"],
        },
        blocking=True,
    )
    mock_channel.send.assert_called_once()
    assert mock_channel.send.call_args[1]["files"] == []


async def test_service_send_embed(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that an embed dict is built into a nextcord.Embed and sent."""
    with patch(
        "homeassistant.components.discord.notify.nextcord.Embed"
    ) as mock_embed_cls:
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "embed test",
                "embed": {"title": "My Title", "description": "Desc", "color": 255},
            },
            blocking=True,
        )
    mock_embed_cls.assert_called_once_with(
        title="My Title", description="Desc", color=255, url=None
    )
    assert mock_channel.send.call_args[1]["embeds"] == [mock_embed]


async def test_service_send_embed_with_fields(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that embed fields each call add_field on the Embed."""
    with patch(
        "homeassistant.components.discord.notify.nextcord.Embed"
    ) as mock_embed_cls:
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "fields",
                "embed": {
                    "fields": [
                        {"name": "F1", "value": "V1"},
                        {"name": "F2", "value": "V2"},
                    ]
                },
            },
            blocking=True,
        )
    assert mock_embed.add_field.call_count == 2


async def test_service_send_embed_with_footer(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that embed footer calls set_footer on the Embed."""
    with patch(
        "homeassistant.components.discord.notify.nextcord.Embed"
    ) as mock_embed_cls:
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "footer",
                "embed": {"footer": {"text": "Footer text"}},
            },
            blocking=True,
        )
    mock_embed.set_footer.assert_called_once_with(text="Footer text")


async def test_service_send_embed_with_author(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that embed author calls set_author on the Embed."""
    with patch(
        "homeassistant.components.discord.notify.nextcord.Embed"
    ) as mock_embed_cls:
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "author",
                "embed": {"author": {"name": "Test Author"}},
            },
            blocking=True,
        )
    mock_embed.set_author.assert_called_once_with(name="Test Author")


async def test_service_send_message_falls_back_to_dm(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test discord.send_message service falls back to DM when channel is not found."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(return_value=mock_channel)

    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {ATTR_ENTITY_ID: ENTITY_ID, "message": "DM via service"},
        blocking=True,
    )

    mock_channel.send.assert_called_once_with("DM via service", files=[], embeds=[])


async def test_service_send_channel_not_found(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
) -> None:
    """Test discord.send_message raises HomeAssistantError when channel and user not found."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {ATTR_ENTITY_ID: ENTITY_ID, "message": "test"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "channel_not_found"


async def test_service_send_http_error(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test discord.send_message raises HomeAssistantError on HTTP error during send."""
    mock_channel.send = AsyncMock(
        side_effect=nextcord.HTTPException(MagicMock(), "rate limited")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {ATTR_ENTITY_ID: ENTITY_ID, "message": "oops"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "send_message_failed"


async def test_service_send_embed_with_thumbnail_and_image(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that embed thumbnail and image call set_thumbnail / set_image."""
    with patch(
        "homeassistant.components.discord.notify.nextcord.Embed"
    ) as mock_embed_cls:
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "message": "thumb+img",
                "embed": {
                    "thumbnail": {"url": "https://example.com/thumb.png"},
                    "image": {"url": "https://example.com/img.png"},
                },
            },
            blocking=True,
        )
    mock_embed.set_thumbnail.assert_called_once_with(
        url="https://example.com/thumb.png"
    )
    mock_embed.set_image.assert_called_once_with(url="https://example.com/img.png")
