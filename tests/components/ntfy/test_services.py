"""Tests for the ntfy notify platform."""

from aiontfy import Message
from yarl import URL

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.components.ntfy.const import (
    ATTR_ATTACH,
    ATTR_CALL,
    ATTR_CLICK,
    ATTR_DELAY,
    ATTR_EMAIL,
    ATTR_ICON,
    ATTR_MARKDOWN,
    ATTR_PRIORITY,
    ATTR_TAGS,
    DOMAIN,
    SERVICE_PUBLISH,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, MockConfigEntry


async def test_ntfy_publish(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message via ntfy.publish action."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUBLISH,
        {
            ATTR_ENTITY_ID: "notify.mytopic",
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "World",
            ATTR_ATTACH: "https://example.org/download.zip",
            ATTR_CALL: "1234567890",
            ATTR_CLICK: "https://example.org",
            ATTR_DELAY: {"days": 1, "seconds": 30},
            ATTR_EMAIL: "mail@example.org",
            ATTR_ICON: "https://example.org/logo.png",
            ATTR_MARKDOWN: True,
            ATTR_PRIORITY: "5",
            ATTR_TAGS: ["partying_face", "grin"],
        },
        blocking=True,
    )

    mock_aiontfy.publish.assert_called_once_with(
        Message(
            topic="mytopic",
            message="Hello",
            title="World",
            tags=["partying_face", "grin"],
            priority=5,
            click=URL("https://example.org"),
            attach=URL("https://example.org/download.zip"),
            markdown=True,
            icon=URL("https://example.org/logo.png"),
            delay="1d 30s",
            email="mail@example.org",
            call="1234567890",
        )
    )
