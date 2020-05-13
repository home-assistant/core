"""The tests for the MaryTTS speech platform."""
import asyncio
import os
import shutil
from urllib.parse import urlencode

from mock import Mock, patch

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import HTTP_INTERNAL_SERVER_ERROR
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant, mock_service


class TestTTSMaryTTSPlatform:
    """Test the speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        asyncio.run_coroutine_threadsafe(
            async_process_ha_core_config(
                self.hass, {"internal_url": "http://example.local:8123"}
            ),
            self.hass.loop,
        )

        self.host = "localhost"
        self.port = 59125
        self.params = {
            "INPUT_TEXT": "HomeAssistant",
            "INPUT_TYPE": "TEXT",
            "OUTPUT_TYPE": "AUDIO",
            "LOCALE": "en_US",
            "AUDIO": "WAVE_FILE",
            "VOICE": "cmu-slt-hsmm",
        }

    def teardown_method(self):
        """Stop everything that was started."""
        default_tts = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        if os.path.isdir(default_tts):
            shutil.rmtree(default_tts)

        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_service_say(self):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        conn = Mock()
        response = Mock()
        conn.getresponse.return_value = response
        response.status = 200
        response.read.return_value = b"audio"

        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch("http.client.HTTPConnection", return_value=conn):
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1
        conn.request.assert_called_with("POST", "/process", urlencode(self.params))

    def test_service_say_with_effect(self):
        """Test service call say with effects."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        conn = Mock()
        response = Mock()
        conn.getresponse.return_value = response
        response.status = 200
        response.read.return_value = b"audio"

        config = {
            tts.DOMAIN: {"platform": "marytts", "effect": {"Volume": "amount:2.0;"}}
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch("http.client.HTTPConnection", return_value=conn):
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1

        self.params.update(
            {"effect_Volume_selected": "on", "effect_Volume_parameters": "amount:2.0;"}
        )
        conn.request.assert_called_with("POST", "/process", urlencode(self.params))

    def test_service_say_http_error(self):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        conn = Mock()
        response = Mock()
        conn.getresponse.return_value = response
        response.status = HTTP_INTERNAL_SERVER_ERROR
        response.reason = "test"
        response.readline.return_value = "content"

        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch("http.client.HTTPConnection", return_value=conn):
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
        self.hass.block_till_done()

        assert len(calls) == 0
        conn.request.assert_called_with("POST", "/process", urlencode(self.params))
