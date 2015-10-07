"""
tests.test_component_media_player
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests media_player component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.core as ha
from homeassistant.const import (
    STATE_OFF,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_VOLUME_UP, SERVICE_VOLUME_DOWN,
    SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PREVIOUS_TRACK, ATTR_ENTITY_ID)
import homeassistant.components.media_player as media_player
from tests.common import mock_service


class TestMediaPlayer(unittest.TestCase):
    """ Test the media_player module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

        self.test_entity = media_player.ENTITY_ID_FORMAT.format('living_room')
        self.hass.states.set(self.test_entity, STATE_OFF)

        self.test_entity2 = media_player.ENTITY_ID_FORMAT.format('bedroom')
        self.hass.states.set(self.test_entity2, "YouTube")

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_is_on(self):
        """ Test is_on method. """
        self.assertFalse(media_player.is_on(self.hass, self.test_entity))
        self.assertTrue(media_player.is_on(self.hass, self.test_entity2))

    def test_services(self):
        """
        Test if the call service methods convert to correct service calls.
        """
        services = {
            SERVICE_TURN_ON: media_player.turn_on,
            SERVICE_TURN_OFF: media_player.turn_off,
            SERVICE_VOLUME_UP: media_player.volume_up,
            SERVICE_VOLUME_DOWN: media_player.volume_down,
            SERVICE_MEDIA_PLAY_PAUSE: media_player.media_play_pause,
            SERVICE_MEDIA_PLAY: media_player.media_play,
            SERVICE_MEDIA_PAUSE: media_player.media_pause,
            SERVICE_MEDIA_NEXT_TRACK: media_player.media_next_track,
            SERVICE_MEDIA_PREVIOUS_TRACK: media_player.media_previous_track
        }

        for service_name, service_method in services.items():
            calls = mock_service(self.hass, media_player.DOMAIN, service_name)

            service_method(self.hass)
            self.hass.pool.block_till_done()

            self.assertEqual(1, len(calls))
            call = calls[-1]
            self.assertEqual(media_player.DOMAIN, call.domain)
            self.assertEqual(service_name, call.service)

            service_method(self.hass, self.test_entity)
            self.hass.pool.block_till_done()

            self.assertEqual(2, len(calls))
            call = calls[-1]
            self.assertEqual(media_player.DOMAIN, call.domain)
            self.assertEqual(service_name, call.service)
            self.assertEqual(self.test_entity,
                             call.data.get(ATTR_ENTITY_ID))
