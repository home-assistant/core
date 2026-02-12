"""Tests for the ntfy notify platform."""

from typing import Any

from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import pytest
import voluptuous as vol
from yarl import URL

from homeassistant.components import camera, image, media_source
from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.components.ntfy.const import DOMAIN
from homeassistant.components.ntfy.services import (
    ATTR_ATTACH,
    ATTR_ATTACH_FILE,
    ATTR_CALL,
    ATTR_CLICK,
    ATTR_DELAY,
    ATTR_EMAIL,
    ATTR_FILENAME,
    ATTR_ICON,
    ATTR_MARKDOWN,
    ATTR_PRIORITY,
    ATTR_SEQUENCE_ID,
    ATTR_TAGS,
    SERVICE_CLEAR,
    SERVICE_DELETE,
    SERVICE_PUBLISH,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import AsyncMock, MockConfigEntry, patch


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
            ATTR_SEQUENCE_ID: "Mc3otamDNcpJ",
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
            sequence_id="Mc3otamDNcpJ",
        ),
        None,
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
        Message(topic="mytopic", message="triggered", title="test"), None
    )


@pytest.mark.parametrize(
    ("exception", "payload", "error_msg"),
    [
        (
            ServiceValidationError,
            {ATTR_DELAY: {"days": 1, "seconds": 30}, ATTR_CALL: "1234567890"},
            "Delayed call notifications are not supported",
        ),
        (
            ServiceValidationError,
            {ATTR_DELAY: {"days": 1, "seconds": 30}, ATTR_EMAIL: "mail@example.org"},
            "Delayed email notifications are not supported",
        ),
        (
            vol.MultipleInvalid,
            {
                ATTR_ATTACH: "https://example.com/Epic Sax Guy 10 Hours.mp4",
                ATTR_ATTACH_FILE: {
                    "media_content_id": "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4",
                    "media_content_type": "video/mp4",
                },
            },
            "Only one attachment source is allowed: URL or local file",
        ),
        (
            vol.MultipleInvalid,
            {
                ATTR_FILENAME: "Epic Sax Guy 10 Hours.mp4",
            },
            "Filename only allowed when attachment is provided",
        ),
    ],
)
async def test_send_message_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    payload: dict[str, Any],
    error_msg: str,
    exception: type[Exception],
) -> None:
    """Test publish message service validation errors."""
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(exception, match=error_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {ATTR_ENTITY_ID: "notify.mytopic", **payload},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "call_method"),
    [
        (SERVICE_PUBLISH, "publish"),
        (SERVICE_CLEAR, "clear"),
        (SERVICE_DELETE, "delete"),
    ],
)
async def test_send_message_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    service: str,
    call_method,
) -> None:
    """Test unauthorized exception initiates reauth flow."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    getattr(mock_aiontfy, call_method).side_effect = (
        NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: "notify.mytopic", ATTR_SEQUENCE_ID: "Mc3otamDNcpJ"},
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


async def test_ntfy_publish_attachment_upload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message via ntfy.publish action with attachment upload."""
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUBLISH,
        {
            ATTR_ENTITY_ID: "notify.mytopic",
            ATTR_ATTACH_FILE: {
                "media_content_id": "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4",
                "media_content_type": "video/mp4",
            },
        },
        blocking=True,
    )

    mock_aiontfy.publish.assert_called_once_with(
        Message(topic="mytopic", filename="Epic Sax Guy 10 Hours.mp4"),
        b"I play the sax\n",
    )


async def test_ntfy_publish_upload_camera_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message via ntfy.publish action with camera snapshot upload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with (
        patch(
            "homeassistant.components.camera.async_get_image",
            return_value=camera.Image("image/jpeg", b"I play the sax\n"),
        ) as mock_get_image,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_ATTACH_FILE: {
                    "media_content_id": "media-source://camera/camera.demo_camera",
                    "media_content_type": "image/jpeg",
                },
                ATTR_FILENAME: "Epic Sax Guy 10 Hours.jpg",
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(hass, "camera.demo_camera")
    mock_aiontfy.publish.assert_called_once_with(
        Message(topic="mytopic", filename="Epic Sax Guy 10 Hours.jpg"),
        b"I play the sax\n",
    )


@pytest.mark.usefixtures("mock_aiontfy")
async def test_ntfy_publish_upload_media_source_not_supported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test publishing ntfy message via ntfy.publish action with unsupported media source."""

    assert await async_setup_component(hass, "tts", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with (
        patch(
            "homeassistant.components.ntfy.notify.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/api/tts_proxy/WDyphPCh3sAoO3koDY87ew.mp3",
                mime_type="audio/mpeg",
                path=None,
            ),
        ),
        pytest.raises(
            ServiceValidationError,
            match="Media source currently not supported",
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_ATTACH_FILE: {
                    "media_content_id": "media-source://tts/demo?message=Hello+world%21&language=en",
                    "media_content_type": "audio/mp3",
                },
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_aiontfy")
async def test_ntfy_publish_upload_media_image_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message with image source."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.image.async_get_image",
        return_value=image.Image(content_type="image/jpeg", content=b"\x89PNG"),
    ) as mock_get_image:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_ATTACH_FILE: {
                    "media_content_id": "media-source://image/image.test",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(hass, "image.test")
    mock_aiontfy.publish.assert_called_once_with(Message(topic="mytopic"), b"\x89PNG")


async def test_ntfy_clear(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test dismiss a ntfy message via ntfy.clear action."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR,
        {
            ATTR_ENTITY_ID: "notify.mytopic",
            ATTR_SEQUENCE_ID: "Mc3otamDNcpJ",
        },
        blocking=True,
    )

    mock_aiontfy.clear.assert_called_once_with("mytopic", "Mc3otamDNcpJ")


@pytest.mark.parametrize(
    "exception",
    [
        NtfyException,
        NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
    ],
)
async def test_clear_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    exception: Exception,
) -> None:
    """Test clear message exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_aiontfy.clear.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_SEQUENCE_ID: "Mc3otamDNcpJ",
            },
            blocking=True,
        )

    mock_aiontfy.clear.assert_called_once_with("mytopic", "Mc3otamDNcpJ")


async def test_ntfy_delete(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test delete a ntfy message via ntfy.delete action."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE,
        {
            ATTR_ENTITY_ID: "notify.mytopic",
            ATTR_SEQUENCE_ID: "Mc3otamDNcpJ",
        },
        blocking=True,
    )

    mock_aiontfy.delete.assert_called_once_with("mytopic", "Mc3otamDNcpJ")


@pytest.mark.parametrize(
    "exception",
    [
        NtfyException,
        NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
    ],
)
async def test_delete_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    exception: Exception,
) -> None:
    """Test delete message exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_aiontfy.delete.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE,
            {
                ATTR_ENTITY_ID: "notify.mytopic",
                ATTR_SEQUENCE_ID: "Mc3otamDNcpJ",
            },
            blocking=True,
        )

    mock_aiontfy.delete.assert_called_once_with("mytopic", "Mc3otamDNcpJ")
