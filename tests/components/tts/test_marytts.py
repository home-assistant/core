"""The tests for the MaryTTS speech platform."""
import asyncio
import os
import shutil

import homeassistant.components.tts as tts
from homeassistant.setup import setup_component
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, DOMAIN as DOMAIN_MP)

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)

from .test_init import mutagen_mock  # noqa


class TestTTSMaryTTSPlatform:
    """Test the speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.url = "http://localhost:59125/process?"
        self.url_param = {
            'INPUT_TEXT': 'HomeAssistant',
            'INPUT_TYPE': 'TEXT',
            'AUDIO': 'WAVE',
            'VOICE': 'cmu-slt-hsmm',
            'OUTPUT_TYPE': 'AUDIO',
            'LOCALE': 'en_US'
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
                'platform': 'marytts'
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_service_say(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(
            self.url, params=self.url_param, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'marytts',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'marytts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
        })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert len(calls) == 1

    def test_service_say_timeout(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(
            self.url, params=self.url_param, status=200,
            exc=asyncio.TimeoutError())

        config = {
            tts.DOMAIN: {
                'platform': 'marytts',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'marytts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    def test_service_say_http_error(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(
            self.url, params=self.url_param, status=403, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'marytts',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'marytts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
        })
        self.hass.block_till_done()

        assert len(calls) == 0
