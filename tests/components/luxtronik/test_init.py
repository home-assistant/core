"""Tests for the luxtronik integration."""

import unittest
from unittest.mock import patch

from homeassistant.components.luxtronik import DOMAIN
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestLuxtronik(unittest.TestCase):
    """Test the Luxtronik integration."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_with_no_host(self):
        """Test setup with no host set."""
        config = {DOMAIN: {}}
        result = setup_component(self.hass, DOMAIN, config)
        assert not result

    @patch("homeassistant.components.luxtronik.Lux")
    def test_setup_with_host(self, mock_luxtronik):
        """Test setup with host set and otherwise default config."""
        config = {DOMAIN: {"host": "192.168.1.100"}}
        result = setup_component(self.hass, DOMAIN, config)
        assert result
        assert mock_luxtronik.called_with("192.168.1.100", 8889, True)

    @patch("homeassistant.components.luxtronik.Lux")
    def test_setup_with_non_default_port(self, mock_luxtronik):
        """Test setup with non standard port."""
        config = {DOMAIN: {"host": "192.168.1.100", "port": 8888}}
        result = setup_component(self.hass, DOMAIN, config)
        assert result
        assert mock_luxtronik.called_with("192.168.1.100", 8888, True)

    @patch("homeassistant.components.luxtronik.Lux")
    def test_setup_with_non_safe_option(self, mock_luxtronik):
        """Test setup with non safe option."""
        config = {DOMAIN: {"host": "192.168.1.100", "safe": False}}
        result = setup_component(self.hass, DOMAIN, config)
        assert result
        assert mock_luxtronik.called_with("192.168.1.100", 8889, False)
