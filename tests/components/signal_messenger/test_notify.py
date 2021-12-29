"""The tests for the signal_messenger platform."""
import base64
import json
import logging
import os
import tempfile
from unittest.mock import patch

from pysignalclirestapi.api import SignalCliRestApiError
import pytest

from homeassistant.setup import async_setup_component

from tests.components.signal_messenger.conftest import (
    CONTENT,
    MESSAGE,
    NUMBER_FROM,
    NUMBERS_TO,
    SIGNAL_SEND_PATH_SUFIX,
    URL_ATTACHMENT,
)

BASE_COMPONENT = "notify"


async def test_signal_messenger_init(hass):
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
    signal_notification_service, signal_requests_mock_factory, caplog
):
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


def test_send_message_should_show_deprecation_warning(
    signal_notification_service, signal_requests_mock_factory, caplog
):
    """Test send message should show deprecation warning."""
    signal_requests_mock = signal_requests_mock_factory()
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.signal_messenger.notify"
    ):
        send_message_with_attachment(signal_notification_service, True)

    assert (
        "The 'attachment' option is deprecated, please replace it with 'attachments'. This option will become invalid in version 0.108"
        in caplog.text
    )
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert_sending_requests(signal_requests_mock, 1)


def test_send_message_with_bad_data_throws_error(
    signal_notification_service, signal_requests_mock_factory, caplog
):
    """Test sending a message with bad data throws an error."""
    signal_requests_mock = signal_requests_mock_factory(False)
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        with pytest.raises(SignalCliRestApiError) as exc:
            signal_notification_service.send_message(MESSAGE)

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert "Couldn't send signal message" in str(exc.value)


def test_send_message_with_attachment(
    signal_notification_service, signal_requests_mock_factory, caplog
):
    """Test send message with attachment."""
    signal_requests_mock = signal_requests_mock_factory()
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        send_message_with_attachment(signal_notification_service, False)

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
    assert_sending_requests(signal_requests_mock, 1)


def send_message_with_attachment(signal_notification_service, deprecated=False):
    """Send message with attachment."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".png", prefix=os.path.basename(__file__)
    ) as tf:
        tf.write("attachment_data")
        data = {"attachment": tf.name} if deprecated else {"attachments": [tf.name]}
        signal_notification_service.send_message(MESSAGE, **{"data": data})


def test_send_message_with_attachment_as_url(
    signal_notification_service, signal_requests_mock_factory, caplog
):
    """Test send message with attachment as URL."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT)))
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        data = {"urls": [URL_ATTACHMENT]}
        signal_notification_service.send_message(MESSAGE, **{"data": data})

    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 3
    assert_sending_requests(signal_requests_mock, 1)


def test_get_attachments(signal_notification_service, signal_requests_mock_factory):
    """Test getting attachments as URL."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT)))
    data = {"urls": [URL_ATTACHMENT]}
    result = signal_notification_service.get_attachments_as_bytes(data, len(CONTENT))

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert result == [bytearray(CONTENT)]


def test_get_attachments_with_large_attachment(
    signal_notification_service, signal_requests_mock_factory
):
    """Test getting attachments as URL with large attachment (per Content-Length header) throws error."""
    signal_requests_mock = signal_requests_mock_factory(True, str(len(CONTENT) + 1))
    with pytest.raises(ValueError) as exc:
        data = {"urls": [URL_ATTACHMENT]}
        signal_notification_service.get_attachments_as_bytes(data, len(CONTENT))

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert "Attachment too large (Content-Length)" in str(exc.value)


def test_get_attachments_with_large_attachment_no_header(
    signal_notification_service, signal_requests_mock_factory
):
    """Test getting attachments as URL with large attachment (per content length) throws error."""
    signal_requests_mock = signal_requests_mock_factory()
    with pytest.raises(ValueError) as exc:
        data = {"urls": [URL_ATTACHMENT]}
        signal_notification_service.get_attachments_as_bytes(data, len(CONTENT) - 1)

    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 1
    assert "Attachment too large (Stream)" in str(exc.value)


def test_get_filenames_with_none_data(signal_notification_service):
    """Test getting filenames with None data returns None."""
    data = None
    result = signal_notification_service.get_filenames(data)

    assert result is None


def test_get_filenames_with_attachments_data(signal_notification_service):
    """Test getting filenames with 'attachments' in data."""
    data = {"attachments": ["test"]}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test"]


def test_get_filenames_with_multiple_attachments_data(signal_notification_service):
    """Test getting filenames with multiple 'attachments' in data."""
    data = {"attachments": ["test", "test2"]}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test", "test2"]


def test_get_filenames_with_attachment_data(signal_notification_service):
    """Test getting filenames with 'attachment' in data."""
    data = {"attachment": "test"}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test"]


def test_get_filenames_with_attachment_and_attachments_data(
    signal_notification_service,
):
    """Test getting filenames with both 'attachment' and 'attachments' in data."""
    data = {"attachment": "test", "attachments": ["test2"]}
    result = signal_notification_service.get_filenames(data)

    assert result == ["test2", "test"]


def assert_sending_requests(signal_requests_mock_factory, attachments_num=0):
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
