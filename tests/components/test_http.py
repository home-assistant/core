"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access,too-many-public-methods
import hashlib
import logging
import unittest
from unittest import mock

import eventlet
import requests

from homeassistant import bootstrap, const
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


def setUpModule():   # pylint: disable=invalid-name
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, 'api')

    hass.start()

    eventlet.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


class TestCollectHash(unittest.TestCase):
    """ tests for http.collect_hash() """

    def setUp(self):
        self.hash = '$a$b$c'
        self.password = 'pass'

    def test_hash_is_prefered_if_both_hash_and_password_are_present(self):
        hash_ = '$1$2$3'
        config = {
            http.CONF_API_PASSWORD: 'pass',
            http.CONF_API_HASH: hash_,
        }
        self.assertEqual(http.split_hash(hash_), http.collect_hash(config))

    def test_returns_new_hash_tuple_if_password_is_present(self):
        salt, password = '2', 'pass'
        config = {http.CONF_API_PASSWORD: password}
        hash_ = http.split_hash(http.new_hash(password, salt))
        with mock.patch('random.sample', return_value=['2']):
            self.assertEqual(http.collect_hash(config), hash_)

    def test_returns_none_if_no_password_or_hash(self):
        self.assertIs(http.collect_hash({}), None)

    def test_returns_hash_tuple_if_hash_is_present(self):
        config = {http.CONF_API_HASH: self.hash}
        self.assertEqual(http.collect_hash(config), ('a', 'b', 'c'))


class TestNewHash(unittest.TestCase):

    def setUp(self):
        self.password = 'password'
        self.new_hash = http.new_hash(self.password, 'aaa')
        self.alg, self.salt, self.hash = http.split_hash(self.new_hash)

    def test_new_hash_returns_random_hash(self):
        hashes = [http.new_hash(self.password)]
        for _ in range(100):
            h = http.new_hash(self.password)
            self.assertNotIn(h, hashes)
            hashes.append(h)

    def test_new_hash_string_has_hash(self):
        hasher = hashlib.sha512()
        hasher.update((self.salt + self.password).encode('utf-8'))
        self.assertEqual(self.hash, hasher.hexdigest())

    def test_new_hash_string_has_salt(self):
        self.assertEqual(self.salt, 'aaa')

    def test_new_hash_string_has_hash_algorithm(self):
        self.assertEqual(self.alg, 'sha512')

    def test_new_hash_returns_dollar_sign_delimited_string(self):
        self.assertEqual(self.new_hash.count('$'), 3)


class TestHttp:
    """Test HTTP component."""

    def test_access_denied_without_password(self):
        """Test access without password."""
        req = requests.get(_url(const.URL_API))

        assert req.status_code == 401

    def test_access_denied_with_wrong_password_in_header(self):
        """Test ascces with wrong password."""
        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: 'wrongpassword'})

        assert req.status_code == 401

    def test_access_with_password_in_header(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.setLevel(logging.WARNING,
                        logger='requests.packages.urllib3.connectionpool')

        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text()

        assert const.URL_API in logs
        assert API_PASSWORD not in logs

    def test_access_denied_with_wrong_password_in_url(self):
        """Test ascces with wrong password."""
        req = requests.get(_url(const.URL_API),
                           params={'api_password': 'wrongpassword'})

        assert req.status_code == 401

    def test_access_with_password_in_url(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.setLevel(logging.WARNING,
                        logger='requests.packages.urllib3.connectionpool')

        req = requests.get(_url(const.URL_API),
                           params={'api_password': API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text()

        assert const.URL_API in logs
        assert API_PASSWORD not in logs
