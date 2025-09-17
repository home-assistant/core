"""Tests for the ntfy notify platform."""

from typing import Any

from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import pytest
from yarl import URL

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.components.ntfy.const import DOMAIN
from homeassistant.components.ntfy.notify import (
    ATTR_ATTACH,
    ATTR_CALL,
    ATTR_CLICK,
    ATTR_DELAY,
    ATTR_EMAIL,
    ATTR_ICON,
    ATTR_MARKDOWN,
    ATTR_PRIORITY,
    ATTR_TAGS,
    SERVICE_PUBLISH,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

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
            ATTR_CLICK: "https://example.org",
            ATTR_DELAY: {"days": 1, "seconds": 30},
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
            delay="86430.0s",
        )
    )


@pytest.mark.parametrize(
    ("exception", "error_msg"),
    [
        (
            NtfyHTTPError(41801, 418, "I'm a teapot", ""),
            "Failed to publish notification: I'm a teapot",
        ),
        (
            NtfyException,
            "Failed to publish notification due to a connection error",
        ),
        (
            NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
            "Failed to authenticate with ntfy service. Please verify your credentials",
        ),
    ],
)
async def test_send_message_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    exception: Exception,
    error_msg: str,
) -> None:
    """Test publish message exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_aiontfy.publish.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_MESSAGE: "triggered",
                ATTR_TITLE: "test",
            },
            blocking=True,
        )

    mock_aiontfy.publish.assert_called_once_with(
        Message(topic="mytopic", message="triggered", title="test")
    )


@pytest.mark.parametrize(
    ("payload", "error_msg"),
    [
        (
            {ATTR_DELAY: {"days": 1, "seconds": 30}, ATTR_CALL: "1234567890"},
            "Delayed call notifications are not supported",
        ),
        (
            {ATTR_DELAY: {"days": 1, "seconds": 30}, ATTR_EMAIL: "mail@example.org"},
            "Delayed email notifications are not supported",
        ),
    ],
)
async def test_send_message_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    payload: dict[str, Any],
    error_msg: str,
) -> None:
    """Test publish message service validation errors."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError, match=error_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {ATTR_ENTITY_ID: "notify.mytopic", **payload},
            blocking=True,
        )


async def test_send_message_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test unauthorized exception initiates reauth flow."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_aiontfy.publish.side_effect = (
        NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_MESSAGE: "triggered",
                ATTR_TITLE: "test",
            },
            blocking=True,
        )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id
