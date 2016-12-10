"""The tests for the TTS component."""

import homeassistant.components.tts as tts
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_MUSIC,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestTTS(object):
    """Test the Google speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_demo(self):
        """Setup the demo platform with defaults."""
        config = {
            tts.DOMAIN: {
                'platform': 'demo',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        assert self.hass.services.has_service(tts.DOMAIN, 'demo_say')

    def test_setup_component_and_test_service(self):
        """Setup the demo platform and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                'platform': 'demo',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'demo_say', {
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        })
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
