"""Tests for the ntfy notify platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
from freezegun.api import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion
from yarl import URL

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
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
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import AsyncMock, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.ntfy.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.usefixtures("mock_aiontfy")
async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the ntfy notify platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@freeze_time("2025-01-09T12:00:00+00:00")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.mytopic")
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.mytopic",
            ATTR_MESSAGE: "triggered",
            ATTR_TITLE: "test",
        },
        blocking=True,
    )

    state = hass.states.get("notify.mytopic")
    assert state
    assert state.state == "2025-01-09T12:00:00+00:00"

    mock_aiontfy.publish.assert_called_once_with(
        Message(topic="mytopic", message="triggered", title="test")
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
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
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
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
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


@freeze_time("2025-01-09T12:00:00+00:00")
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

    state = hass.states.get("notify.mytopic")
    assert state
    assert state.state == STATE_UNKNOWN

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

    state = hass.states.get("notify.mytopic")
    assert state
    assert state.state == "2025-01-09T12:00:00+00:00"

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
