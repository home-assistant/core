"""The tests for the rss_feed_api component."""
import json
import unittest
from xml.etree import ElementTree

import requests

from homeassistant import setup, const
import homeassistant.core as ha
import homeassistant.components.http as http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

hass = None


def _url(path=""):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test1', 'a_state_1')
    hass.states.set('test.test2', 'a_state_2')
    hass.states.set('test.test3', 'a_state_3')

    setup.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    setup.setup_component(
        hass, 'rss_feed_template',
        { 'rss_feed_template':
         {'testfeed': {
             'title':'feed title is {{states.test.test1.state}}',
             'items': [{'title':'item title is {{states.test.test2.state}}',
                        'description':'desc {{states.test.test3.state}}'}]}}})

    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


class TestRssFeedTemplate(unittest.TestCase):
    """Test the API."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_rss_get_feed(self):
        """Test if we can retrieve the correct rss feed."""
        req = requests.get(_url('/api/rss/testfeed'),
                           headers=HA_HEADERS)

        xml=ElementTree.fromstring(req.text)
        self.assertEqual('feed title is a_state_1',
                         xml[0].text)
        self.assertEqual('item title is a_state_2',
                         xml[1][0].text)
        self.assertEqual('desc a_state_3',
                         xml[1][1].text)
