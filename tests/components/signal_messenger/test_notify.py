"""The tests for the signal_messenger platform."""

import os
import tempfile
import unittest
from unittest.mock import patch

from pysignalclirestapi import SignalCliRestApi
import requests_mock

import homeassistant.components.signal_messenger.notify as signalmessenger
from homeassistant.setup import async_setup_component

BASE_COMPONENT = "notify"


async def test_signal_messenger_init(hass):
    """Test that service loads successfully."""

    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "signal_messenger",
            "url": "http://127.0.0.1:8080",
            "number": "+43443434343",
            "recipients": ["+435565656565"],
        }
    }

    with patch("pysignalclirestapi.SignalCliRestApi.send_message", return_value=None):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test that service loads successfully
        assert hass.services.has_service(BASE_COMPONENT, "test")


class TestSignalMesssenger(unittest.TestCase):
    """Test the signal_messenger notify."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        recipients = ["+435565656565"]
        number = "+43443434343"
        client = SignalCliRestApi("http://127.0.0.1:8080", number)
        self._signalmessenger = signalmessenger.SignalNotificationService(
            recipients, client
        )

    @requests_mock.Mocker()
    def test_send_message(self, mock):
        """Test send message."""
        message = "Testing Signal Messenger platform :)"
        mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with self.assertLogs(
            "homeassistant.components.signal_messenger.notify", level="DEBUG"
        ) as context:
            self._signalmessenger.send_message(message)
        self.assertIn("Sending signal message", context.output[0])
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 2)

    @requests_mock.Mocker()
    def test_send_message_should_show_deprecation_warning(self, mock):
        """Test send message."""
        message = "Testing Signal Messenger platform with attachment :)"
        mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with self.assertLogs(
            "homeassistant.components.signal_messenger.notify", level="WARNING"
        ) as context:
            with tempfile.NamedTemporaryFile(
                suffix=".png", prefix=os.path.basename(__file__)
            ) as tf:
                data = {"data": {"attachment": tf.name}}
                self._signalmessenger.send_message(message, **data)
        self.assertIn(
            "The 'attachment' option is deprecated, please replace it with 'attachments'. This option will become invalid in version 0.108",
            context.output[0],
        )
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 2)

    @requests_mock.Mocker()
    def test_send_message_with_attachment(self, mock):
        """Test send message."""
        message = "Testing Signal Messenger platform :)"
        mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with self.assertLogs(
            "homeassistant.components.signal_messenger.notify", level="DEBUG"
        ) as context:
            with tempfile.NamedTemporaryFile(
                suffix=".png", prefix=os.path.basename(__file__)
            ) as tf:
                data = {"data": {"attachments": [tf.name]}}
                self._signalmessenger.send_message(message, **data)
        self.assertIn("Sending signal message", context.output[0])
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 2)
