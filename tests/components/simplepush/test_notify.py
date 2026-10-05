"""Test Simplepush notifications."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from simplepush import ApiError
from simplepush.legacy import BadRequest, UnknownError

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.simplepush.const import (
    CONF_DEVICE_KEY,
    CONF_SALT,
    CONF_TOPIC,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_TOKEN, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_DEVICE_KEY: "abc",
    CONF_NAME: "simplepush",
}

APP_CONFIG = {CONF_API_TOKEN: "token"}

MOVED_CONFIG = {
    CONF_API_TOKEN: "token",
    CONF_NAME: "simplepush",
    CONF_TOPIC: "abc",
}

ENTITY_ID = "notify.simplepush"

SERVICE_NAME = "simplepush"


@pytest.fixture
def mock_send() -> Generator[MagicMock]:
    """Mock the simplepush send call."""
    with patch("homeassistant.components.simplepush.notify.send") as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the simplepush client of the current app."""
    with patch("homeassistant.components.simplepush.Client") as mock:
        yield mock


async def setup_config_entry(
    hass: HomeAssistant, data: dict[str, str]
) -> MockConfigEntry:
    """Set up the simplepush integration."""
    entry = MockConfigEntry(domain=DOMAIN, title="simplepush", data=data)
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


async def setup_app_entry(
    hass: HomeAssistant, data: dict[str, str], title: str = "Simplepush"
) -> MockConfigEntry:
    """Set up an entry of the current app."""
    entry = MockConfigEntry(domain=DOMAIN, title=title, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def send_entity_message(hass: HomeAssistant, data: dict[str, str]) -> None:
    """Send a message through the notify entity."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("data", "title", "topic"),
    [
        pytest.param(APP_CONFIG, "Simplepush", None, id="new_entry"),
        pytest.param(MOVED_CONFIG, "simplepush", "abc", id="moved_entry"),
    ],
)
async def test_entity_send_message(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: MagicMock,
    data: dict[str, str],
    title: str,
    topic: str | None,
) -> None:
    """Test sending a message through the notify entity."""
    entry = await setup_app_entry(hass, data, title)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == entry.entry_id

    await send_entity_message(hass, {ATTR_MESSAGE: "Hello", ATTR_TITLE: "Title"})
    await send_entity_message(hass, {ATTR_MESSAGE: "Hello"})

    mock_client.assert_called_once_with(api_token="token")
    assert mock_client.return_value.send_task.call_args_list == [
        call(topic=topic, title="Title", content="Hello", links=None),
        call(topic=topic, title="Home Assistant", content="Hello", links=None),
    ]


@pytest.mark.usefixtures("mock_client")
async def test_new_entry_has_no_legacy_action(hass: HomeAssistant) -> None:
    """Test that an entry of the current app only gets the notify entity."""
    await setup_app_entry(hass, APP_CONFIG)

    assert hass.states.get(ENTITY_ID) is not None
    assert not hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)


@pytest.mark.parametrize(
    ("data", "side_effect", "translation_key"),
    [
        pytest.param(
            APP_CONFIG, ApiError(401, ""), "invalid_api_token", id="invalid_token"
        ),
        pytest.param(
            MOVED_CONFIG, ApiError(403, ""), "topic_not_joined", id="not_holder"
        ),
        pytest.param(
            APP_CONFIG, ApiError(403, ""), "send_message_failed", id="own_devices_403"
        ),
        pytest.param(
            APP_CONFIG, ApiError(500, ""), "send_message_failed", id="server_error"
        ),
        pytest.param(APP_CONFIG, OSError, "send_message_failed", id="network_error"),
    ],
)
async def test_entity_send_message_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    data: dict[str, str],
    side_effect: Exception | type[Exception],
    translation_key: str,
) -> None:
    """Test that a failing send through the current app raises."""
    await setup_app_entry(hass, data, "simplepush")
    mock_client.return_value.send_task.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await send_entity_message(hass, {ATTR_MESSAGE: "Hello"})

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


IMAGE = "https://example.com/image.jpg"
VIDEO = "https://example.com/video.mp4"


async def test_moved_entry_legacy_action(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the legacy action of an entry moved from the old app."""
    await setup_app_entry(hass, MOVED_CONFIG, "simplepush")
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)
    assert not issue_registry.issues

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {
            "message": "Hello",
            "data": {"attachments": [{"image": IMAGE}, {"video": VIDEO}]},
        },
        blocking=True,
    )

    mock_client.return_value.send_task.assert_called_once_with(
        topic="abc", title="Home Assistant", content="Hello", links=[IMAGE, VIDEO]
    )
    assert "were not sent" not in caplog.text
    issue = issue_registry.async_get_issue(
        NOTIFY_DOMAIN, f"migrate_notify_{DOMAIN}_{SERVICE_NAME}"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.4.0"


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
            {"attachments": [{"image": "not a URL"}, {"video": VIDEO}]},
            [VIDEO],
            "Thumbnails and attachments without an image or video URL",
            id="not_a_url",
        ),
        pytest.param(
            {"event": "event"},
            None,
            "Events are not supported by the Simplepush app",
            id="event",
        ),
    ],
)
async def test_moved_entry_ignored_data(
    hass: HomeAssistant,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service_data: dict[str, Any],
    expected_links: list[str] | None,
    warning: str,
) -> None:
    """Test that data of the old app the current app can't show is left out."""
    await setup_app_entry(hass, MOVED_CONFIG, "simplepush")

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", "data": service_data},
        blocking=True,
    )

    mock_client.return_value.send_task.assert_called_once_with(
        topic="abc", title="Home Assistant", content="Hello", links=expected_links
    )
    assert warning in caplog.text


async def test_move_switches_service_without_restart(
    hass: HomeAssistant, mock_send: MagicMock, mock_client: MagicMock
) -> None:
    """Test that moving an old app entry switches its action on reload."""
    entry = await setup_config_entry(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID) is None

    hass.config_entries.async_update_entry(entry, data=MOVED_CONFIG)
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
    assert hass.states.get(ENTITY_ID) is not None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(MOCK_CONFIG, id="old_app"),
        pytest.param(APP_CONFIG, id="new_entry"),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_unload(hass: HomeAssistant, data: dict[str, str]) -> None:
    """Test unloading an entry."""
    entry = await setup_app_entry(hass, data, "simplepush")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)
