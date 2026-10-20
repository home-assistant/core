"""Test Simplepush notifications."""

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from simplepush import ApiError
from simplepush.legacy import BadRequest, UnknownError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.simplepush.const import CONF_DEVICE_KEY, CONF_SALT, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

MOCK_CONFIG = {
    CONF_DEVICE_KEY: "abc",
    CONF_NAME: "simplepush",
}

SERVICE_NAME = "simplepush"


async def setup_config_entry(hass: HomeAssistant, data: dict[str, str]) -> None:
    """Set up the simplepush integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)


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
    mock_legacy_send: MagicMock,
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

    mock_legacy_send.assert_called_once_with(
        key="abc",
        title="Home Assistant",
        message="Hello",
        attachments=expected_attachments,
        event=expected_event,
    )


async def test_send_message_with_password(
    hass: HomeAssistant, mock_legacy_send: MagicMock
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

    mock_legacy_send.assert_called_once_with(
        key="abc",
        password="password",
        salt="salt",
        title="Home Assistant",
        message="Hello",
        attachments=None,
        event=None,
    )


async def test_send_message_with_invalid_attachment(
    hass: HomeAssistant, mock_legacy_send: MagicMock, caplog: pytest.LogCaptureFixture
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
    mock_legacy_send.assert_not_called()


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
    mock_legacy_send: MagicMock,
    side_effect: type[Exception],
    expected_exception: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Test that a failing send raises the correct exception."""
    await setup_config_entry(hass, MOCK_CONFIG)
    mock_legacy_send.side_effect = side_effect

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


ENTITY_ID = "notify.simplepush"


async def send_entity_message(hass: HomeAssistant, data: dict[str, str]) -> None:
    """Send a message through the notify entity."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )


@pytest.mark.usefixtures("mock_client")
async def test_notify_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the notify entity of the current app."""
    await setup_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_entity_send_message(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test sending a message through the notify entity of the current app."""
    await setup_integration(hass, config_entry)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == config_entry.entry_id
    assert not hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)

    await send_entity_message(hass, {ATTR_MESSAGE: "Hello", ATTR_TITLE: "Title"})
    await send_entity_message(hass, {ATTR_MESSAGE: "Hello"})

    mock_client.assert_called_once_with(api_token="token")
    assert mock_client.return_value.send_task.call_args_list == [
        call(title="Title", content="Hello"),
        call(title=None, content="Hello"),
    ]


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(ApiError(401, ""), "invalid_api_token", id="invalid_token"),
        pytest.param(ApiError(500, ""), "send_message_failed", id="server_error"),
        pytest.param(OSError, "send_message_failed", id="network_error"),
    ],
)
async def test_entity_send_message_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception | type[Exception],
    translation_key: str,
) -> None:
    """Test that a failing send through the current app raises."""
    await setup_integration(hass, config_entry)
    mock_client.return_value.send_task.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await send_entity_message(hass, {ATTR_MESSAGE: "Hello"})

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
