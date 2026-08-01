"""Test Simplepush notifications."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from simplepush import BadRequest, UnknownError

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.simplepush.const import CONF_DEVICE_KEY, CONF_SALT, DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_DEVICE_KEY: "abc",
    CONF_NAME: "simplepush",
}

SERVICE_NAME = "simplepush"


@pytest.fixture
def mock_send() -> Generator[MagicMock]:
    """Mock the simplepush send call."""
    with patch("homeassistant.components.simplepush.notify.send") as mock:
        yield mock


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
