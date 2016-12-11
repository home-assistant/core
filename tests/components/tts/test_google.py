"""The tests for the Google speech platform."""
import asyncio
from unittest.mock import patch

import homeassistant.components.tts as tts
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, DOMAIN as DOMAIN_MP)
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestTTSGooglePlatform(object):
    """Test the Google speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            tts.DOMAIN: {
                'platform': 'google',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    @patch('gtts_token.gtts_token.Token.calculate_token', autospec=True,
           return_value=5)
    def test_service_say(self, mock_calculate, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url = ("http://translate.google.com/translate_tts?tl=en&"
               "q=I%20person%20is%20on%20front%20of%20your%20door."
               "&tk=5&client=hass&textlen=48")

        aioclient_mock.get(url, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'google',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'google_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1

    @patch('gtts_token.gtts_token.Token.calculate_token', autospec=True,
           return_value=5)
    def test_service_say_error(self, mock_calculate, aioclient_mock):
        """Test service call say with http response 400."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url = ("http://translate.google.com/translate_tts?tl=en&"
               "q=I%20person%20is%20on%20front%20of%20your%20door."
               "&tk=5&client=hass&textlen=48")

        aioclient_mock.get(url, status=400, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'google',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'google_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    @patch('gtts_token.gtts_token.Token.calculate_token', autospec=True,
           return_value=5)
    def test_service_say_timeout(self, mock_calculate, aioclient_mock):
        """Test service call say with http timeout."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url = ("http://translate.google.com/translate_tts?tl=en&"
               "q=I%20person%20is%20on%20front%20of%20your%20door."
               "&tk=5&client=hass&textlen=48")

        aioclient_mock.get(url, exc=asyncio.TimeoutError())

        config = {
            tts.DOMAIN: {
                'platform': 'google',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'google_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1
