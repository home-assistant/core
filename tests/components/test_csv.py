"""The tests for the csv component."""
import datetime
import os
import tempfile

import unittest
from unittest import mock

import homeassistant.components.csv as csvcomp
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant


class TestCsv(unittest.TestCase):
    """Test the csv component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.handler_method = None
        self.hass.bus.listen = mock.Mock()

    def tearDown(self):
        """Clear data."""
        self.hass.stop()

    def test_setup_minimal_config(self):
        """Test the setup with minimal configuration."""
        with tempfile.TemporaryDirectory() as tempdirname:
            config = {
                'csv': {
                    'data_dir': tempdirname
                }
            }
            assert setup_component(self.hass, csvcomp.DOMAIN, config)

    def test_setup_full_config(self):
        """Test the setup with full configuration."""
        with tempfile.TemporaryDirectory() as tempdirname:
            config = {
                'csv': {
                    'data_dir': tempdirname,
                    'include': {
                        'entities': [
                            'sensor.include'
                        ],
                        'domains': [
                            'sun'
                        ]
                    },
                    'exclude': {
                        'entities': [
                            'sensor.exclude'
                        ],
                        'domains': [
                            'weather'
                        ]
                    }
                }
            }
            assert setup_component(self.hass, csvcomp.DOMAIN, config)

    def test_lines_written(self):
        """Test that csv file gets created and filled."""
        with tempfile.TemporaryDirectory() as tempdir:
            config = {
                'csv': {
                    'data_dir': tempdir
                }
            }
            assert setup_component(self.hass, csvcomp.DOMAIN, config)

            self.hass.states.set('sensor.temperature', 10)

            self.hass.block_till_done()
            self.hass.data[csvcomp.DOMAIN].block_till_done()

            now = datetime.datetime.now()
            file_name = 'events_' + now.strftime("%Y-%m-%d") + '.csv'
            path = os.path.join(tempdir, file_name)
            self.assertTrue(os.path.isfile(path))

            line_found = False
            with open(path, 'r') as file:
                for line in file:
                    if "sensor.temperature" in line and "10" in line:
                        line_found = True
            self.assertTrue(line_found)

            self.hass.block_till_done()

    def test_lines_written_separator(self):
        """Test that csv file gets created and filled."""
        with tempfile.TemporaryDirectory() as tempdir:
            config = {
                'csv': {
                    'data_dir': tempdir,
                    'separator': ';'
                }
            }
            assert setup_component(self.hass, csvcomp.DOMAIN, config)

            self.hass.states.set('sensor.temperature', 10)

            self.hass.block_till_done()
            self.hass.data[csvcomp.DOMAIN].block_till_done()

            now = datetime.datetime.now()
            file_name = 'events_' + now.strftime("%Y-%m-%d") + '.csv'
            path = os.path.join(tempdir, file_name)
            self.assertTrue(os.path.isfile(path))

            line_found = False
            with open(path, 'r') as file:
                for line in file:
                    if "sensor.temperature;" in line and "10" in line:
                        line_found = True
            self.assertTrue(line_found)

            self.hass.block_till_done()
