"""The tests for the Yandex SpeechKit speech platform."""
import asyncio
import os
import shutil

import homeassistant.components.tts as tts
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, ATTR_MEDIA_CONTENT_ID, DOMAIN as DOMAIN_MP)
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestTTSYandexPlatform(object):
    """Test the speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

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
                'platform': 'yandextts',
                'api_key': '1234567xx'
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_setup_component_without_api_key(self):
        """Test setup component without api key."""
        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
            }
        }

        with assert_setup_component(0, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

