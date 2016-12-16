"""The tests for the Updater component."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
import os

import requests
import requests_mock
import voluptuous as vol

from homeassistant.bootstrap import setup_component
from homeassistant.components import updater

from tests.common import (
    assert_setup_component, fire_time_changed, get_test_home_assistant)

NEW_VERSION = '10000.0'

# We need to use a 'real' looking version number to load the updater component
MOCK_CURRENT_VERSION = '10.0'


class TestUpdater(unittest.TestCase):
    """Test the Updater component."""

    hass = None

    def setup_method(self, _):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.updater.get_newest_version')
    def test_new_version_shows_entity_on_start(  # pylint: disable=invalid-name
            self, mock_get_newest_version):
        """Test if new entity is created if new version is available."""
        mock_get_newest_version.return_value = (NEW_VERSION, '')
        updater.CURRENT_VERSION = MOCK_CURRENT_VERSION

        with assert_setup_component(1) as config:
            setup_component(self.hass, updater.DOMAIN, {updater.DOMAIN: {}})
            _dt = datetime.now() + timedelta(hours=1)
            assert config['updater'] == {'reporting': True}

        for secs in [-1, 0, 1]:
            fire_time_changed(self.hass, _dt + timedelta(seconds=secs))
            self.hass.block_till_done()

        self.assertTrue(self.hass.states.is_state(
            updater.ENTITY_ID, NEW_VERSION))

    @patch('homeassistant.components.updater.get_newest_version')
    def test_no_entity_on_same_version(  # pylint: disable=invalid-name
            self, mock_get_newest_version):
        """Test if no entity is created if same version."""
        mock_get_newest_version.return_value = (MOCK_CURRENT_VERSION, '')
        updater.CURRENT_VERSION = MOCK_CURRENT_VERSION

        with assert_setup_component(1) as config:
            assert setup_component(
                self.hass, updater.DOMAIN, {updater.DOMAIN: {}})
            _dt = datetime.now() + timedelta(hours=1)
            assert config['updater'] == {'reporting': True}

        self.assertIsNone(self.hass.states.get(updater.ENTITY_ID))

        mock_get_newest_version.return_value = (NEW_VERSION, '')

        for secs in [-1, 0, 1]:
            fire_time_changed(self.hass, _dt + timedelta(seconds=secs))
            self.hass.block_till_done()

        self.assertTrue(self.hass.states.is_state(
            updater.ENTITY_ID, NEW_VERSION))

    @patch('homeassistant.components.updater.requests.post')
    def test_errors_while_fetching_new_version(  # pylint: disable=invalid-name
            self, mock_get):
        """Test for errors while fetching the new version."""
        mock_get.side_effect = requests.RequestException
        uuid = '0000'
        self.assertIsNone(updater.get_newest_version(uuid))

        mock_get.side_effect = ValueError
        self.assertIsNone(updater.get_newest_version(uuid))

        mock_get.side_effect = vol.Invalid('Expected dictionary')
        self.assertIsNone(updater.get_newest_version(uuid))

    def test_uuid_function(self):
        """Test if the uuid function works."""
        path = self.hass.config.path(updater.UPDATER_UUID_FILE)
        try:
            # pylint: disable=protected-access
            uuid = updater._load_uuid(self.hass)
            assert os.path.isfile(path)
            uuid2 = updater._load_uuid(self.hass)
            assert uuid == uuid2
            os.remove(path)
            uuid2 = updater._load_uuid(self.hass)
            assert uuid != uuid2
        finally:
            os.remove(path)

    @requests_mock.Mocker()
    def test_reporting_false_works(self, m):
        """Test we do not send any data."""
        m.post(updater.UPDATER_URL,
               json={'version': '0.15',
                     'release-notes': 'https://home-assistant.io'})

        response = updater.get_newest_version(None)

        assert response == ('0.15', 'https://home-assistant.io')

        history = m.request_history

        assert len(history) == 1
        assert history[0].json() == {}

    @patch('homeassistant.components.updater.get_newest_version')
    def test_error_during_fetch_works(
            self, mock_get_newest_version):
        """Test if no entity is created if same version."""
        mock_get_newest_version.return_value = None

        updater.check_newest_version(self.hass, None)

        self.assertIsNone(self.hass.states.get(updater.ENTITY_ID))
