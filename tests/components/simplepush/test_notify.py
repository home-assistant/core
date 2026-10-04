"""Test Simplepush notifications."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from simplepush import ApiError
from simplepush.legacy import BadRequest, UnknownError

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.simplepush.const import (
    CONF_DEVICE_KEY,
    CONF_SALT,
    CONF_TOPIC,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_DEVICE_KEY: "abc",
    CONF_NAME: "simplepush",
}

APP_CONFIG = {
    CONF_API_TOKEN: "token",
    CONF_NAME: "simplepush",
}

SERVICE_NAME = "simplepush"


@pytest.fixture
def mock_send() -> Generator[MagicMock]:
    """Mock the simplepush send call."""
    with patch("homeassistant.components.simplepush.notify.send") as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the simplepush client of the current app."""
    with patch("homeassistant.components.simplepush.notify.Client") as mock:
        yield mock


async def setup_config_entry(
    hass: HomeAssistant, data: dict[str, str]
) -> MockConfigEntry:
    """Set up the simplepush integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)
    return entry


@pytest.mark.parametrize(
    ("service_data", "expected_attachments", "expected_event"),
    [
        pytest.param({}, None, None, id="message_only"),
        pytest.param({"data": {"event": "event"}}, None, "event", id="event_in_data"),
        pytest.param(
            {"data": {"attachments": "image.jpg"}},
            None,
            None,
            id="attachments_not_a_list",
        ),
        pytest.param(
            {"data": {"attachments": [{"image": "image.jpg"}]}},
            ["image.jpg"],
            None,
            id="image_attachment",
        ),
        pytest.param(
            {"data": {"attachments": [{"video": "video.mp4"}]}},
            ["video.mp4"],
            None,
            id="video_attachment",
        ),
        pytest.param(
            {
                "data": {
                    "attachments": [{"video": "video.mp4", "thumbnail": "thumb.jpg"}]
                }
            },
            [{"video": "video.mp4", "thumbnail": "thumb.jpg"}],
            None,
            id="video_attachment_with_thumbnail",
        ),
    ],
)
async def test_send_message(
    hass: HomeAssistant,
    mock_send: MagicMock,
    service_data: dict[str, Any],
    expected_attachments: list[Any] | None,
    expected_event: str | None,
) -> None:
    """Test sending a message."""
    await setup_config_entry(hass, MOCK_CONFIG)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", **service_data},
        blocking=True,
    )

    mock_send.assert_called_once_with(
        key="abc",
        title="Home Assistant",
        message="Hello",
        attachments=expected_attachments,
        event=expected_event,
    )


async def test_send_message_with_password(
    hass: HomeAssistant, mock_send: MagicMock
) -> None:
    """Test sending a message with an encryption password."""
    await setup_config_entry(
        hass, {**MOCK_CONFIG, CONF_PASSWORD: "password", CONF_SALT: "salt"}
    )

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello"},
        blocking=True,
    )

    mock_send.assert_called_once_with(
        key="abc",
        password="password",
        salt="salt",
        title="Home Assistant",
        message="Hello",
        attachments=None,
        event=None,
    )


async def test_send_message_with_invalid_attachment(
    hass: HomeAssistant, mock_send: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid attachment format sends nothing."""
    await setup_config_entry(hass, MOCK_CONFIG)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", "data": {"attachments": [{"file": "image.jpg"}]}},
        blocking=True,
    )

    assert "Attachment format is incorrect" in caplog.text
    mock_send.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "expected_exception", "translation_key"),
    [
        pytest.param(
            BadRequest,
            ServiceValidationError,
            "title_or_message_too_long",
            id="bad_request",
        ),
        pytest.param(
            UnknownError,
            HomeAssistantError,
            "send_message_failed",
            id="unknown_error",
        ),
    ],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_send: MagicMock,
    side_effect: type[Exception],
    expected_exception: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Test that a failing send raises the correct exception."""
    await setup_config_entry(hass, MOCK_CONFIG)
    mock_send.side_effect = side_effect

    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            {"message": "Hello"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


async def test_no_discovery_info(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup of the legacy platform without discovery info."""
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {NOTIFY_DOMAIN: {"platform": DOMAIN}},
    )
    await hass.async_block_till_done()

    assert f"Failed to initialize notification service {DOMAIN}" in caplog.text
    assert not hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)


@pytest.mark.parametrize(
    ("data", "topic"),
    [
        pytest.param(APP_CONFIG, None, id="own_devices"),
        pytest.param({**APP_CONFIG, CONF_TOPIC: "abc"}, "abc", id="topic"),
    ],
)
async def test_send_app_message(
    hass: HomeAssistant,
    mock_client: MagicMock,
    data: dict[str, str],
    topic: str | None,
) -> None:
    """Test sending a message through the current app."""
    await setup_config_entry(hass, data)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello"},
        blocking=True,
    )

    mock_client.assert_called_once_with(api_token="token")
    mock_client.return_value.send_task.assert_called_once_with(
        topic=topic, title="Home Assistant", content="Hello", links=None
    )


IMAGE = "https://example.com/image.jpg"
VIDEO = "https://example.com/video.mp4"


@pytest.mark.parametrize(
    ("service_data", "expected_links"),
    [
        pytest.param({"links": [IMAGE, VIDEO]}, [IMAGE, VIDEO], id="links"),
        pytest.param({"links": IMAGE}, [IMAGE], id="single_link"),
        pytest.param(
            {"attachments": [{"image": IMAGE}, {"video": VIDEO}]},
            [IMAGE, VIDEO],
            id="attachments",
        ),
        pytest.param(
            {"links": [IMAGE], "attachments": [{"video": VIDEO}]},
            [IMAGE, VIDEO],
            id="links_and_attachments",
        ),
    ],
)
async def test_send_app_message_links(
    hass: HomeAssistant,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service_data: dict[str, Any],
    expected_links: list[str],
) -> None:
    """Test that links and the old app's attachments become links of the task."""
    await setup_config_entry(hass, APP_CONFIG)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", "data": service_data},
        blocking=True,
    )

    mock_client.return_value.send_task.assert_called_once_with(
        topic=None, title="Home Assistant", content="Hello", links=expected_links
    )
    assert "were not sent" not in caplog.text


@pytest.mark.parametrize(
    ("service_data", "expected_links", "warning"),
    [
        pytest.param(
            {"attachments": [{"video": VIDEO, "thumbnail": IMAGE}]},
            [VIDEO],
            "Thumbnails and attachments without an image or video URL",
            id="thumbnail",
        ),
        pytest.param(
            {"attachments": [IMAGE]},
            None,
            "Thumbnails and attachments without an image or video URL",
            id="not_a_dict",
        ),
        pytest.param(
            {"event": "event"},
            None,
            "Events are not supported by the Simplepush app",
            id="event",
        ),
    ],
)
async def test_send_app_message_ignored_data(
    hass: HomeAssistant,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service_data: dict[str, Any],
    expected_links: list[str] | None,
    warning: str,
) -> None:
    """Test that data of the old app the current app can't show is left out."""
    await setup_config_entry(hass, APP_CONFIG)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", "data": service_data},
        blocking=True,
    )

    mock_client.return_value.send_task.assert_called_once_with(
        topic=None, title="Home Assistant", content="Hello", links=expected_links
    )
    assert warning in caplog.text


@pytest.mark.parametrize(
    "links",
    [pytest.param(5, id="number"), pytest.param([IMAGE, 5], id="list_with_number")],
)
async def test_send_app_message_invalid_links(
    hass: HomeAssistant, mock_client: MagicMock, links: Any
) -> None:
    """Test that links other than URLs are rejected."""
    await setup_config_entry(hass, APP_CONFIG)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            {"message": "Hello", "data": {"links": links}},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_links"
    mock_client.return_value.send_task.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(ApiError(401, ""), "invalid_api_token", id="invalid_token"),
        pytest.param(ApiError(403, ""), "topic_not_joined", id="not_holder"),
        pytest.param(ApiError(500, ""), "send_message_failed", id="server_error"),
        pytest.param(OSError, "send_message_failed", id="network_error"),
    ],
)
async def test_send_app_message_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    translation_key: str,
) -> None:
    """Test that a failing send through the current app raises."""
    await setup_config_entry(hass, APP_CONFIG)
    mock_client.return_value.send_task.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            {"message": "Hello"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


async def test_reload_replaces_service(
    hass: HomeAssistant, mock_send: MagicMock, mock_client: MagicMock
) -> None:
    """Test that moving an old app entry switches the service without a restart."""
    entry = await setup_config_entry(hass, MOCK_CONFIG)

    hass.config_entries.async_update_entry(
        entry, data={**APP_CONFIG, CONF_TOPIC: "abc"}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello"},
        blocking=True,
    )

    mock_send.assert_not_called()
    mock_client.return_value.send_task.assert_called_once_with(
        topic="abc", title="Home Assistant", content="Hello", links=None
    )
