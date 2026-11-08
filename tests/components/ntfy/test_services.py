"""Tests for the ntfy notify platform."""

from typing import Any

from aiontfy import BroadcastAction, HttpAction, Message, ViewAction
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import probatio
import pytest
from pytest_homeassistant.common import AsyncMock, MockConfigEntry, patch
from yarl import URL

from homeassistant.components import media_source
from homeassistant.components.ntfy.const import DOMAIN, NtfyService, NtfyServiceArgument
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component


@pytest.mark.freeze_time("2026-01-01T23:59:59+00:00")
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
        NtfyService.PUBLISH,
        {
            CommonServiceArgument.ENTITY_ID: "notify.mytopic",
            NtfyServiceArgument.MESSAGE: "Hello",
            NtfyServiceArgument.TITLE: "World",
            NtfyServiceArgument.ATTACH: "https://example.org/download.zip",
            NtfyServiceArgument.CLICK: "https://example.org",
            NtfyServiceArgument.DELAY: {"days": 1, "seconds": 30},
            NtfyServiceArgument.ICON: "https://example.org/logo.png",
            NtfyServiceArgument.MARKDOWN: True,
            NtfyServiceArgument.PRIORITY: "5",
            NtfyServiceArgument.TAGS: ["partying_face", "grin"],
            NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
            NtfyServiceArgument.ACTIONS: [
                {
                    "action": "broadcast",
                    "label": "Take picture",
                    "intent": "com.example.AN_INTENT",
                    "extras": {"cmd": "pic"},
                    "clear": True,
                },
                {
                    "action": "view",
                    "label": "Open website",
                    "url": "https://example.com",
                    "clear": False,
                },
                {
                    "action": "http",
                    "label": "Close door",
                    "url": "https://api.example.local/",
                    "method": "PUT",
                    "headers": {"Authorization": "Bearer ..."},
                    "clear": False,
                },
            ],
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
            actions=[
                BroadcastAction(
                    label="Take picture",
                    intent="com.example.AN_INTENT",
                    extras={"cmd": "pic"},
                    clear=True,
                ),
                ViewAction(
                    label="Open website",
                    url=URL("https://example.com"),
                    clear=False,
                ),
                HttpAction(
                    label="Close door",
                    url=URL("https://api.example.local/"),
                    method="PUT",
                    headers={"Authorization": "Bearer ..."},
                    body=None,
                    clear=False,
                ),
            ],
        ),
        None,
    )

    state = hass.states.get("notify.mytopic")
    assert state
    assert state.state == "2026-01-01T23:59:59+00:00"


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
            NtfyService.PUBLISH,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.MESSAGE: "triggered",
                NtfyServiceArgument.TITLE: "test",
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
            {
                NtfyServiceArgument.DELAY: {"days": 1, "seconds": 30},
                NtfyServiceArgument.CALL: "1234567890",
            },
            "Delayed call notifications are not supported",
        ),
        (
            ServiceValidationError,
            {
                NtfyServiceArgument.DELAY: {"days": 1, "seconds": 30},
                NtfyServiceArgument.EMAIL: "mail@example.org",
            },
            "Delayed email notifications are not supported",
        ),
        (
            probatio.MultipleInvalid,
            {
                NtfyServiceArgument.ATTACH: "https://example.com/Epic Sax Guy 10 Hours.mp4",
                NtfyServiceArgument.ATTACH_FILE: {
                    "media_content_id": (
                        "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
                    ),
                    "media_content_type": "video/mp4",
                },
            },
            "Only one attachment source is allowed: URL or local file",
        ),
        (
            probatio.MultipleInvalid,
            {
                NtfyServiceArgument.FILENAME: "Epic Sax Guy 10 Hours.mp4",
            },
            "Filename only allowed when attachment is provided",
        ),
        (
            probatio.MultipleInvalid,
            {
                NtfyServiceArgument.ACTIONS: [
                    {"action": "broadcast", "label": "1"},
                    {"action": "broadcast", "label": "2"},
                    {"action": "broadcast", "label": "3"},
                    {"action": "broadcast", "label": "4"},
                ],
            },
            "Too many actions defined. A maximum of 3 is supported",
        ),
        (
            probatio.MultipleInvalid,
            {NtfyServiceArgument.ACTIONS: [{"action": "copy", "label": "Copy"}]},
            r"required key not provided at 'actions\[0\]\.value'",
        ),
    ],
)
@pytest.mark.usefixtures("mock_aiontfy")
async def test_send_message_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
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
            NtfyService.PUBLISH,
            {CommonServiceArgument.ENTITY_ID: "notify.mytopic", **payload},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "call_method"),
    [
        (NtfyService.PUBLISH, "publish"),
        (NtfyService.CLEAR, "clear"),
        (NtfyService.DELETE, "delete"),
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
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
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
        NtfyService.PUBLISH,
        {
            CommonServiceArgument.ENTITY_ID: "notify.mytopic",
            NtfyServiceArgument.ATTACH_FILE: {
                "media_content_id": (
                    "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
                ),
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
    """Test ntfy.publish action with camera snapshot upload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with (
        patch(
            "homeassistant.components.ntfy.notify.async_get_media_image",
            return_value=media_source.MediaImage(b"I play the sax\n", "image/jpeg"),
        ) as mock_get_image,
    ):
        await hass.services.async_call(
            DOMAIN,
            NtfyService.PUBLISH,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.ATTACH_FILE: {
                    "media_content_id": "media-source://camera/camera.demo_camera",
                    "media_content_type": "image/jpeg",
                },
                NtfyServiceArgument.FILENAME: "Epic Sax Guy 10 Hours.jpg",
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(
        hass, "media-source://camera/camera.demo_camera"
    )
    mock_aiontfy.publish.assert_called_once_with(
        Message(topic="mytopic", filename="Epic Sax Guy 10 Hours.jpg"),
        b"I play the sax\n",
    )


@pytest.mark.usefixtures("mock_aiontfy")
async def test_ntfy_publish_upload_media_source_not_supported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test ntfy.publish action with unsupported media source."""

    assert await async_setup_component(hass, "tts", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with (
        patch(
            "homeassistant.components.ntfy.notify.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="https://gameclipscontent-d2009.media.xboxlive.com/123456789",
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
            NtfyService.PUBLISH,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.ATTACH_FILE: {
                    "media_content_id": "media-source://xbox/123456789/",
                    "media_content_type": "video/mp4",
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
        "homeassistant.components.ntfy.notify.async_get_media_image",
        return_value=media_source.MediaImage(b"\x89PNG", "image/jpeg"),
    ) as mock_get_image:
        await hass.services.async_call(
            DOMAIN,
            NtfyService.PUBLISH,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.ATTACH_FILE: {
                    "media_content_id": "media-source://image/image.test",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(hass, "media-source://image/image.test")
    mock_aiontfy.publish.assert_called_once_with(Message(topic="mytopic"), b"\x89PNG")


@pytest.mark.usefixtures("mock_aiontfy")
async def test_ntfy_publish_upload_tts_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
) -> None:
    """Test publishing ntfy message with tts source."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.tts.async_get_media_source_audio",
        return_value=("mp3", b"Test"),
    ) as mock_get_media_source_audio:
        await hass.services.async_call(
            DOMAIN,
            NtfyService.PUBLISH,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.ATTACH_FILE: {
                    "media_content_id": "media-source://tts/demo?message=Test&language=en",
                    "media_content_type": "audio/mp3",
                },
            },
            blocking=True,
        )
    mock_get_media_source_audio.assert_called_once_with(
        hass, "media-source://tts/demo?message=Test&language=en"
    )
    mock_aiontfy.publish.assert_called_once_with(Message(topic="mytopic"), b"Test")


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
        NtfyService.CLEAR,
        {
            CommonServiceArgument.ENTITY_ID: "notify.mytopic",
            NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
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
            NtfyService.CLEAR,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
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
        NtfyService.DELETE,
        {
            CommonServiceArgument.ENTITY_ID: "notify.mytopic",
            NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
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
            NtfyService.DELETE,
            {
                CommonServiceArgument.ENTITY_ID: "notify.mytopic",
                NtfyServiceArgument.SEQUENCE_ID: "Mc3otamDNcpJ",
            },
            blocking=True,
        )

    mock_aiontfy.delete.assert_called_once_with("mytopic", "Mc3otamDNcpJ")
