"""The tests for the apprise notification platform."""
import os
import unittest
from unittest.mock import patch
from tempfile import mkdtemp

from apprise import Apprise
from apprise import AppriseConfig

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from tests.common import assert_setup_component, get_test_home_assistant


class TestApprise(unittest.TestCase):
    """Tests the Apprise Component."""

    tmp_dir = None

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.tmp_dir = mkdtemp()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()
        for fname in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, fname))
        os.rmdir(self.tmp_dir)

    @patch.object(AppriseConfig, "add", return_value=False)
    def test_apprise_config_bad_conf_add(self, __mockcfg_add):
        """Test set up the platform with bad/missing file configuration."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "config": "/path/"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    @patch.object(Apprise, "add", return_value=False)
    @patch.object(AppriseConfig, "add", return_value=True)
    def test_apprise_config_bad_conf_save(self, __mock_add, __mockcfg_add):
        """Test set up the platform failing to save config data."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "config": "/path/"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    @patch.object(Apprise, "add", return_value=False)
    def test_apprise_bad_url(self, __mock_notify):
        """Test set up the platform with bad/missing configuration."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "url": "dbus://"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    def test_apprise_config_bad_url(self):
        """Test set up the platform with bad/missing url configuration."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "apprise",
                # Expects an actual URL
                "url": 1,
            }
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    @patch.object(Apprise, "notify", return_value=True)
    def test_apprise_url(self, __mock_notify):
        """Test simple apprise push using URL config."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "url": "windows://"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        data = {"title": "Test Title", "message": "Test Message"}
        assert not self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()

    @patch.object(Apprise, "notify", return_value=True)
    def test_apprise_config(self, __mock_notify):
        """Test simple apprise push using AppriseConfig."""
        tmp_cfg = os.path.join(self.tmp_dir, "apprise.txt")
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "config": tmp_cfg}
        }

        with open(tmp_cfg, "w+") as f:
            # Write a simple text based configuration file
            f.write("windows://")

        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        data = {"title": "Test Title", "message": "Test Message"}
        assert not self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
