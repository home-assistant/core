"""The tests for the signal_messenger platform."""

import base64
import json
import logging
import os
import tempfile
from unittest.mock import patch

from pysignalclirestapi.api import SignalCliRestApiError
import pytest
from requests_mock.mocker import Mocker
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    CONTENT,
    MESSAGE,
    NUMBER_FROM,
    NUMBERS_TO,
    SIGNAL_SEND_PATH_SUFIX,
    URL_ATTACHMENT,
    SignalNotificationService,
)

BASE_COMPONENT = "notify"


async def test_signal_messenger_init(hass: HomeAssistant) -> None:
    """Test that service loads successfully."""
    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "signal_messenger",
            "url": "http://127.0.0.1:8080",
            "number": NUMBER_FROM,
            "recipients": NUMBERS_TO,
        }
    }

    with patch("pysignalclirestapi.SignalCliRestApi.send_message", return_value=None):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        assert hass.services.has_service(BASE_COMPONENT, "test")


def test_send_message(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message."""
    signal_requests_mock = signal_requests_mock_factory()
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        signal_notification_service.send_message(MESSAGE)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert_sending_requests(signal_requests_mock)


def test_send_message_styled(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send styled message."""
    signal_requests_mock = signal_requests_mock_factory()
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        data = {"text_mode": "styled"}
        signal_notification_service.send_message(MESSAGE, data=data)
    post_data = json.loads(signal_requests_mock.request_history[-1].text)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert post_data["text_mode"] == "styled"
    assert_sending_requests(signal_requests_mock)


def test_send_message_to_api_with_bad_data_throws_error(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a message with bad data to the API throws an error."""
    signal_requests_mock = signal_requests_mock_factory(False)
    with (
        caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ),
        pytest.raises(SignalCliRestApiError) as exc,
    ):
        signal_notification_service.send_message(MESSAGE)

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert "Couldn't send signal message" in str(exc.value)


def test_send_message_with_bad_data_throws_vol_error(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a message with bad data throws an error."""
    with (
        caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ),
        pytest.raises(vol.Invalid) as exc,
    ):
        signal_notification_service.send_message(MESSAGE, data={"test": "test"})

    assert "Sending signal message" in caplog.text
    assert "extra keys not allowed" in str(exc.value)


def test_send_message_styled_with_bad_data_throws_vol_error(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a styled message with bad data throws an error."""
    with (
        caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ),
        pytest.raises(vol.Invalid) as exc,
    ):
        signal_notification_service.send_message(MESSAGE, data={"text_mode": "test"})

    assert "Sending signal message" in caplog.text
    assert (
        "value must be one of ['normal', 'styled'] for dictionary value @ data['text_mode']"
        in str(exc.value)
    )


def test_send_message_with_attachment(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message with attachment."""
    signal_requests_mock = signal_requests_mock_factory()
    with (
        caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ),
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".png", prefix=os.path.basename(__file__)
        ) as temp_file,
    ):
        temp_file.write("attachment_data")
        data = {"attachments": [temp_file.name]}
        signal_notification_service.send_message(MESSAGE, data=data)

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert_sending_requests(signal_requests_mock, 1)


def test_send_message_styled_with_attachment(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message with attachment."""
    signal_requests_mock = signal_requests_mock_factory()
    with (
        caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ),
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".png", prefix=os.path.basename(__file__)
        ) as temp_file,
    ):
        temp_file.write("attachment_data")
        data = {"attachments": [temp_file.name], "text_mode": "styled"}
        signal_notification_service.send_message(MESSAGE, data=data)
    post_data = json.loads(signal_requests_mock.request_history[-1].text)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert_sending_requests(signal_requests_mock, 1)
    assert post_data["text_mode"] == "styled"


def test_send_message_with_attachment_as_url(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message with attachment as URL."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT)))
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        data = {"urls": [URL_ATTACHMENT]}
        signal_notification_service.send_message(MESSAGE, data=data)

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 3
    assert_sending_requests(signal_requests_mock, 1)


def test_send_message_styled_with_attachment_as_url(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message with attachment as URL."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT)))
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        data = {"urls": [URL_ATTACHMENT], "text_mode": "styled"}
        signal_notification_service.send_message(MESSAGE, data=data)
    post_data = json.loads(signal_requests_mock.request_history[-1].text)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 3
    assert_sending_requests(signal_requests_mock, 1)
    assert post_data["text_mode"] == "styled"


def test_get_attachments(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT)))
    data = {"urls": [URL_ATTACHMENT]}
    result = signal_notification_service.get_attachments_as_bytes(
        data, len(CONTENT), hass
    )

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert result == [bytearray(CONTENT)]


def test_get_attachments_not_on_allowlist(
    signal_notification_service: SignalNotificationService,
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL that aren't on the allowlist."""
    url = "http://dodgyurl.com"
    data = {"urls": [url]}
    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.signal_messenger.notify"
    ):
        result = signal_notification_service.get_attachments_as_bytes(
            data, len(CONTENT), hass
        )

    assert f"URL '{url}' not in allow list" in caplog.text
    assert result is None


def test_get_attachments_with_large_attachment(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with large attachment (per Content-Length header) throws error."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT) + 1))
    with pytest.raises(ValueError) as exc:
        signal_notification_service.get_attachments_as_bytes(
            {"urls": [URL_ATTACHMENT]}, len(CONTENT), hass
        )

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert "Attachment too large (Content-Length reports" in str(exc.value)


def test_get_attachments_with_large_attachment_no_header(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with large attachment (per content length) throws error."""
    signal_requests_mock = signal_requests_mock_factory()
    with pytest.raises(ValueError) as exc:
        signal_notification_service.get_attachments_as_bytes(
            {"urls": [URL_ATTACHMENT]}, len(CONTENT) - 1, hass
        )

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert "Attachment too large (Stream reports" in str(exc.value)


def test_get_filenames_with_none_data(
    signal_notification_service: SignalNotificationService,
) -> None:
    """Test getting filenames with None data returns None."""
    data = None
    result = signal_notification_service.get_filenames(data)

    assert result is None


def test_get_filenames_with_attachments_data(
    signal_notification_service: SignalNotificationService,
) -> None:
    """Test getting filenames with 'attachments' in data."""
    data = {"attachments": ["test"]}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test"]


def test_get_filenames_with_multiple_attachments_data(
    signal_notification_service: SignalNotificationService,
) -> None:
    """Test getting filenames with multiple 'attachments' in data."""
    data = {"attachments": ["test", "test2"]}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test", "test2"]


def test_get_filenames_with_non_list_returns_none(
    signal_notification_service: SignalNotificationService,
) -> None:
    """Test getting filenames with non list data."""
    data = {"attachments": "test"}
    result = signal_notification_service.get_filenames(data)

    assert result is None


def test_get_attachments_with_non_list_returns_none(
    signal_notification_service: SignalNotificationService,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments with non list data."""
    data = {"urls": URL_ATTACHMENT}
    result = signal_notification_service.get_attachments_as_bytes(
        data, len(CONTENT), hass
    )

    assert result is None


def test_get_attachments_with_verify_unset(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with verify_ssl unset results in verify=true."""
    signal_requests_mock = signal_requests_mock_factory()
    data = {"urls": [URL_ATTACHMENT]}
    signal_notification_service.get_attachments_as_bytes(data, len(CONTENT), hass)

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert signal_requests_mock.last_request.verify is True


def test_get_attachments_with_verify_set_true(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with verify_ssl set to true results in verify=true."""
    signal_requests_mock = signal_requests_mock_factory()
    data = {"verify_ssl": True, "urls": [URL_ATTACHMENT]}
    signal_notification_service.get_attachments_as_bytes(data, len(CONTENT), hass)

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert signal_requests_mock.last_request.verify is True


def test_get_attachments_with_verify_set_false(
    signal_notification_service: SignalNotificationService,
    signal_requests_mock_factory: Mocker,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with verify_ssl set to false results in verify=false."""
    signal_requests_mock = signal_requests_mock_factory()
    data = {"verify_ssl": False, "urls": [URL_ATTACHMENT]}
    signal_notification_service.get_attachments_as_bytes(data, len(CONTENT), hass)

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert signal_requests_mock.last_request.verify is False


def test_get_attachments_with_verify_set_garbage(
    signal_notification_service: SignalNotificationService,
    hass: HomeAssistant,
) -> None:
    """Test getting attachments as URL with verify_ssl set to garbage results in None."""
    data = {"verify_ssl": "test", "urls": [URL_ATTACHMENT]}
    result = signal_notification_service.get_attachments_as_bytes(
        data, len(CONTENT), hass
    )

    assert result is None


def assert_sending_requests(
    signal_requests_mock_factory: Mocker, attachments_num: int = 0
) -> None:
    """Assert message was send with correct parameters."""
    send_request = signal_requests_mock_factory.request_history[-1]
    assert send_request.path == SIGNAL_SEND_PATH_SUFIX

    body_request = json.loads(send_request.text)
    assert body_request["message"] == MESSAGE
    assert body_request["number"] == NUMBER_FROM
    assert body_request["recipients"] == NUMBERS_TO
    assert len(body_request["base64_attachments"]) == attachments_num

    for attachment in body_request["base64_attachments"]:
        if len(attachment) > 0:
            assert base64.b64decode(attachment) == CONTENT
