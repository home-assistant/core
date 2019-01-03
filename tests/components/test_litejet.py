"""The tests for the litejet component."""
import logging
import unittest

from homeassistant.components import litejet
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestLiteJet(unittest.TestCase):
    """Test the litejet component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_ignored_unspecified(self):
        """Ensure it is ignored when unspecified."""
        self.hass.data['litejet_config'] = {}
        assert not litejet.is_ignored(self.hass, 'Test')

    def test_is_ignored_empty(self):
        """Ensure it is ignored when empty."""
        self.hass.data['litejet_config'] = {
            litejet.CONF_EXCLUDE_NAMES: []
        }
        assert not litejet.is_ignored(self.hass, 'Test')

    def test_is_ignored_normal(self):
        """Test if usually ignored."""
        self.hass.data['litejet_config'] = {
            litejet.CONF_EXCLUDE_NAMES: ['Test', 'Other One']
        }
        assert litejet.is_ignored(self.hass, 'Test')
        assert not litejet.is_ignored(self.hass, 'Other one')
        assert not litejet.is_ignored(self.hass, 'Other 0ne')
        assert litejet.is_ignored(self.hass, 'Other One There')
        assert litejet.is_ignored(self.hass, 'Other One')
