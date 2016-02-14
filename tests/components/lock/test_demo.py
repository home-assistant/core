"""
tests.components.lock.test_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo lock component.
"""
import unittest

from homeassistant.components import lock

from tests.common import get_test_home_assistant


FRONT = 'lock.front_door'
KITCHEN = 'lock.kitchen_door'


class TestLockDemo(unittest.TestCase):
    """ Test the demo lock. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        self.assertTrue(lock.setup(self.hass, {
            'lock': {
                'platform': 'demo'
            }
        }))

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_is_locked(self):
        self.assertTrue(lock.is_locked(self.hass, FRONT))
        self.hass.states.is_state(FRONT, 'locked')

        self.assertFalse(lock.is_locked(self.hass, KITCHEN))
        self.hass.states.is_state(KITCHEN, 'unlocked')

    def test_locking(self):
        lock.lock(self.hass, KITCHEN)

        self.hass.pool.block_till_done()

        self.assertTrue(lock.is_locked(self.hass, KITCHEN))

    def test_unlocking(self):
        lock.unlock(self.hass, FRONT)

        self.hass.pool.block_till_done()

        self.assertFalse(lock.is_locked(self.hass, FRONT))
