"""The tests for the litejet component."""
import logging
import unittest

from homeassistant.components import litejet
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestLiteJet(unittest.TestCase):
    """Test the litejet component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_ignored_unspecified(self):
        self.hass.data['litejet_config'] = {}
        assert not litejet.is_ignored(self.hass, 'Test')

    def test_is_ignored_empty(self):
        self.hass.data['litejet_config'] = {
            litejet.CONF_EXCLUDE_NAMES: []
        }
        assert not litejet.is_ignored(self.hass, 'Test')

    def test_is_ignored_normal(self):
        self.hass.data['litejet_config'] = {
            litejet.CONF_EXCLUDE_NAMES: ['Test', 'Other One']
        }
        assert litejet.is_ignored(self.hass, 'Test')
        assert not litejet.is_ignored(self.hass, 'Other one')
        assert not litejet.is_ignored(self.hass, 'Other 0ne')
        assert litejet.is_ignored(self.hass, 'Other One There')
        assert litejet.is_ignored(self.hass, 'Other One')
