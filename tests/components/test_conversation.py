"""
tests.components.test_conversation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Conversation component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.components as core_components
import homeassistant.components.conversation as conversation
import homeassistant.components.demo as demo
import homeassistant.components.light as light

from common import get_test_home_assistant


class TestConversation(unittest.TestCase):
    """ Test the conversation component. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Start up ha for testing """
        self.hass = get_test_home_assistant(3)
        demo.setup(self.hass, {demo.DOMAIN: {}})
        core_components.setup(self.hass, {})

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup_and_turn_on(self):
        """ Setup and perform good turn on requests """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        light.turn_off(self.hass, 'light.kitchen_lights')

        event_data = {conversation.ATTR_TEXT: 'turn kitchen lights on'}
        self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True)

        self.assertTrue(
            light.is_on(self.hass, 'light.kitchen_lights'))

    def test_setup_and_turn_off(self):
        """ Setup and perform good turn off requests """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        light.turn_on(self.hass, 'light.kitchen_lights')

        event_data = {conversation.ATTR_TEXT: 'turn kitchen lights off'}
        self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True)

        self.assertFalse(
            light.is_on(self.hass, 'light.kitchen_lights'))

    def test_setup_and_bad_request_format(self):
        """ Setup and perform a badly formatted request """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        event_data = {
            conversation.ATTR_TEXT:
            'what is the answer to the ultimate question of life, ' +
            'the universe and everything'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))

    def test_setup_and_bad_request_entity(self):
        """ Setup and perform requests with bad entity id """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        event_data = {conversation.ATTR_TEXT: 'turn something off'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))

    def test_setup_and_bad_request_command(self):
        """ Setup and perform requests with bad command """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        event_data = {conversation.ATTR_TEXT: 'turn kitchen over'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))

    def test_setup_and_bad_request_notext(self):
        """ Setup and perform requests with bad command with no text """
        self.assertTrue(
            conversation.setup(self.hass, {conversation.DOMAIN: {}}))

        event_data = {}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))
