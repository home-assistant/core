"""The tests for the Demo lock platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components import lock

from tests.common import get_test_home_assistant, mock_service
from tests.components.lock import common

FRONT = 'lock.front_door'
KITCHEN = 'lock.kitchen_door'
OPENABLE_LOCK = 'lock.openable_lock'


class TestLockDemo(unittest.TestCase):
    """Test the demo lock."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        assert setup_component(self.hass, lock.DOMAIN, {
            'lock': {
                'platform': 'demo'
            }
        })

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_locked(self):
        """Test if lock is locked."""
        assert lock.is_locked(self.hass, FRONT)
        self.hass.states.is_state(FRONT, 'locked')

        assert not lock.is_locked(self.hass, KITCHEN)
        self.hass.states.is_state(KITCHEN, 'unlocked')

    def test_locking(self):
        """Test the locking of a lock."""
        common.lock(self.hass, KITCHEN)
        self.hass.block_till_done()

        assert lock.is_locked(self.hass, KITCHEN)

    def test_unlocking(self):
        """Test the unlocking of a lock."""
        common.unlock(self.hass, FRONT)
        self.hass.block_till_done()

        assert not lock.is_locked(self.hass, FRONT)

    def test_opening(self):
        """Test the opening of a lock."""
        calls = mock_service(self.hass, lock.DOMAIN, lock.SERVICE_OPEN)
        common.open_lock(self.hass, OPENABLE_LOCK)
        self.hass.block_till_done()
        assert 1 == len(calls)
