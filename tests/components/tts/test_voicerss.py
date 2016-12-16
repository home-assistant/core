"""The tests for the VoiceRSS speech platform."""
import asyncio
import os
import shutil

import homeassistant.components.tts as tts
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, ATTR_MEDIA_CONTENT_ID, DOMAIN as DOMAIN_MP)
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestTTSVoiceRSSPlatform(object):
    """Test the voicerss speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.url = "https://api.voicerss.org/"
        self.url_param = {
            'key': '1234567xx',
            'hl': 'en-us',
            'c': 'MP3',
            'f': '8khz_8bit_mono',
        }

    def teardown_method(self):
        """Stop everything that was started."""
        default_tts = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        if os.path.isdir(default_tts):
            shutil.rmtree(default_tts)

        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
                'api_key': '1234567xx'
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_setup_component_without_api_key(self):
        """Test setup component without api key."""
        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
            }
        }

        with assert_setup_component(0, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_service_say(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.post(
            self.url, params=self.url_param, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
                'api_key': '1234567xx',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'voicerss_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1

    def test_service_say_german(self, aioclient_mock):
        """Test service call say with german code."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        self.url_param['hl'] = 'de-de'
        aioclient_mock.post(
            self.url, params=self.url_param, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
                'api_key': '1234567xx',
                'language': 'de-de',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'voicerss_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1

    def test_service_say_error(self, aioclient_mock):
        """Test service call say with http response 400."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.post(
            self.url, params=self.url_param, status=400, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
                'api_key': '1234567xx',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'voicerss_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    def test_service_say_timeout(self, aioclient_mock):
        """Test service call say with http timeout."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.post(
            self.url, params=self.url_param, exc=asyncio.TimeoutError())

        config = {
            tts.DOMAIN: {
                'platform': 'voicerss',
                'api_key': '1234567xx',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'voicerss_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1
