"""The tests for the Updater component."""
import unittest
from unittest.mock import patch
import os

import requests

from homeassistant.bootstrap import setup_component
from homeassistant.components import updater
import homeassistant.util.dt as dt_util

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
            assert setup_component(
                self.hass, updater.DOMAIN, {updater.DOMAIN: {}})
            assert config['updater'] == {'opt_out': False}

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
            assert config['updater'] == {'opt_out': False}

        self.assertIsNone(self.hass.states.get(updater.ENTITY_ID))

        mock_get_newest_version.return_value = (NEW_VERSION, '')

        fire_time_changed(
            self.hass, dt_util.utcnow().replace(hour=0, minute=0, second=0))

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

        mock_get.side_effect = KeyError
        self.assertIsNone(updater.get_newest_version(uuid))

    def test_updater_disabled_on_dev(self):
        """Test if the updater component is disabled on dev."""
        updater.CURRENT_VERSION = MOCK_CURRENT_VERSION + 'dev'

        with assert_setup_component(1) as config:
            assert not setup_component(
                self.hass, updater.DOMAIN, {updater.DOMAIN: {}})
            assert config['updater'] == {'opt_out': False}

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
