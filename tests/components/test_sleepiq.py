"""The tests for the SleepIQ component."""
import unittest
from unittest.mock import MagicMock, patch

import requests_mock

from homeassistant import setup
import homeassistant.components.sleepiq as sleepiq

from tests.common import load_fixture, get_test_home_assistant


def mock_responses(mock):
    """Mock responses for SleepIQ."""
    base_url = 'https://api.sleepiq.sleepnumber.com/rest/'
    mock.put(
        base_url + 'login',
        text=load_fixture('sleepiq-login.json'))
    mock.get(
        base_url + 'bed?_k=0987',
        text=load_fixture('sleepiq-bed.json'))
    mock.get(
        base_url + 'sleeper?_k=0987',
        text=load_fixture('sleepiq-sleeper.json'))
    mock.get(
        base_url + 'bed/familyStatus?_k=0987',
        text=load_fixture('sleepiq-familystatus.json'))


class TestSleepIQ(unittest.TestCase):
    """Tests the SleepIQ component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.username = 'foo'
        self.password = 'bar'
        self.config = {
            'sleepiq': {
                'username': self.username,
                'password': self.password,
            }
        }

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test the setup."""
        mock_responses(mock)

        # We're mocking the load_platform discoveries or else the platforms
        # will be setup during tear down when blocking till done, but the mocks
        # are no longer active.
        with patch(
                'homeassistant.helpers.discovery.load_platform', MagicMock()):
            assert sleepiq.setup(self.hass, self.config)

    @requests_mock.Mocker()
    def test_setup_login_failed(self, mock):
        """Test the setup if a bad username or password is given."""
        mock.put('https://api.sleepiq.sleepnumber.com/rest/login',
                 status_code=401,
                 json=load_fixture('sleepiq-login-failed.json'))

        response = sleepiq.setup(self.hass, self.config)
        self.assertFalse(response)

    def test_setup_component_no_login(self):
        """Test the setup when no login is configured."""
        conf = self.config.copy()
        del conf['sleepiq']['username']
        assert not setup.setup_component(self.hass, sleepiq.DOMAIN, conf)

    def test_setup_component_no_password(self):
        """Test the setup when no password is configured."""
        conf = self.config.copy()
        del conf['sleepiq']['password']

        assert not setup.setup_component(self.hass, sleepiq.DOMAIN, conf)
