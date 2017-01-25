"""The tests for the zwave component."""
import unittest
from unittest.mock import MagicMock, patch

from homeassistant.bootstrap import setup_component
from homeassistant.components import zwave
from tests.common import get_test_home_assistant


class TestComponentZwave(unittest.TestCase):
    """Test the Zwave component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def _validate_config(self, validator, config):
        libopenzwave = MagicMock()
        libopenzwave.__file__ = 'test'
        with patch.dict('sys.modules', {
            'libopenzwave': libopenzwave,
            'openzwave.option': MagicMock(),
            'openzwave.network': MagicMock(),
            'openzwave.group': MagicMock(),
        }):
            validator(setup_component(self.hass, zwave.DOMAIN, {
                zwave.DOMAIN: config,
            }))

    def test_empty_config(self):
        """Test empty config."""
        self._validate_config(self.assertTrue, {})

    def test_empty_customize(self):
        """Test empty customize."""
        self._validate_config(self.assertTrue, {'customize': {}})
        self._validate_config(self.assertTrue, {'customize': []})

    def test_empty_customize_content(self):
        """Test empty customize."""
        self._validate_config(
            self.assertTrue, {'customize': {'test.test': {}}})

    def test_full_customize_dict(self):
        """Test full customize as dict."""
        self._validate_config(self.assertTrue, {'customize': {'test.test': {
            zwave.CONF_POLLING_INTENSITY: 10,
            zwave.CONF_IGNORED: 1,
            zwave.CONF_REFRESH_VALUE: 1,
            zwave.CONF_REFRESH_DELAY: 10}}})

    def test_full_customize_list(self):
        """Test full customize as list."""
        self._validate_config(self.assertTrue, {'customize': [{
            'entity_id': 'test.test',
            zwave.CONF_POLLING_INTENSITY: 10,
            zwave.CONF_IGNORED: 1,
            zwave.CONF_REFRESH_VALUE: 1,
            zwave.CONF_REFRESH_DELAY: 10}]})

    def test_bad_customize(self):
        """Test customize with extra keys."""
        self._validate_config(
            self.assertFalse, {'customize': {'test.test': {'extra_key': 10}}})
