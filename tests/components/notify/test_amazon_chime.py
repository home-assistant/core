"""The tests for the Amazon Chime notification platform."""
import unittest
import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
import homeassistant.components.notify.amazon_chime as amazon_chime

from tests.common import (
    assert_setup_component, get_test_home_assistant)


class TestAmazonChime(unittest.TestCase):
    """Tests the AmazonChime Component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.webhook_url = 'https://myfakeapikey.local?token=1234'
        self.amazon_chime = amazon_chime.AmazonChime(self.webhook_url)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()

    def test_amazon_chime_config(self):
        """Test setup."""
        config = {notify.DOMAIN: {'name': 'test',
                                  'platform': 'amazon_chime',
                                  'url': 'https://myfakeapikey.com'}}
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    def test_amazon_chime_config_bad(self):
        """Test set up the platform with bad/missing configuration."""
        config = {
            notify.DOMAIN: {
                'platform': 'amazon_chime',
            }
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    @requests_mock.Mocker()
    def test_send_simple_message(self, mock):
        """Test sending a simple message with success."""
        mock.register_uri(
            requests_mock.POST,
            self.webhook_url,
            status_code=200
        )

        message = "This is a Test"

        self.amazon_chime.send_message(message=message)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "Content": message
        }
        assert mock.last_request.json() == expected_body

        expected_params = {'token': ['1234']}
        assert mock.last_request.qs == expected_params

    @requests_mock.Mocker()
    def test_send_simple_message_with_all_members(self, mock):
        """Test sending a simple message with all members."""
        mock.register_uri(
            requests_mock.POST,
            self.webhook_url,
            status_code=200
        )

        message = "This is a Test"
        data = {
            "all_members": True
        }
        self.amazon_chime.send_message(message=message, data=data)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "Content": message + ' @All'
        }
        assert mock.last_request.json() == expected_body

        expected_params = {'token': ['1234']}
        assert mock.last_request.qs == expected_params

    @requests_mock.Mocker()
    def test_send_simple_message_with_present_members(self, mock):
        """Test sending a simple message with present members."""
        mock.register_uri(
            requests_mock.POST,
            self.webhook_url,
            status_code=200
        )

        message = "This is a Test"
        data = {
            "present_members": True
        }
        self.amazon_chime.send_message(message=message, data=data)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "Content": message + ' @Present'
        }
        assert mock.last_request.json() == expected_body

        expected_params = {'token': ['1234']}
        assert mock.last_request.qs == expected_params
