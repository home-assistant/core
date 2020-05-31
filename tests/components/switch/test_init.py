"""The tests for the Switch component."""
# pylint: disable=protected-access
import unittest

from homeassistant import core
from homeassistant.components import switch
from homeassistant.const import CONF_PLATFORM
from homeassistant.setup import async_setup_component, setup_component

from tests.common import get_test_home_assistant, mock_entity_platform
from tests.components.switch import common


class TestSwitch(unittest.TestCase):
    """Test the switch module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        platform = getattr(self.hass.components, "test.switch")
        platform.init()
        # Switch 1 is ON, switch 2 is OFF
        self.switch_1, self.switch_2, self.switch_3 = platform.ENTITIES

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_methods(self):
        """Test is_on, turn_on, turn_off methods."""
        assert setup_component(
            self.hass, switch.DOMAIN, {switch.DOMAIN: {CONF_PLATFORM: "test"}}
        )
        assert switch.is_on(self.hass, self.switch_1.entity_id)
        assert not switch.is_on(self.hass, self.switch_2.entity_id)
        assert not switch.is_on(self.hass, self.switch_3.entity_id)

        common.turn_off(self.hass, self.switch_1.entity_id)
        common.turn_on(self.hass, self.switch_2.entity_id)

        self.hass.block_till_done()

        assert not switch.is_on(self.hass, self.switch_1.entity_id)
        assert switch.is_on(self.hass, self.switch_2.entity_id)

        # Turn all off
        common.turn_off(self.hass)

        self.hass.block_till_done()

        assert not switch.is_on(self.hass, self.switch_1.entity_id)
        assert not switch.is_on(self.hass, self.switch_2.entity_id)
        assert not switch.is_on(self.hass, self.switch_3.entity_id)

        # Turn all on
        common.turn_on(self.hass)

        self.hass.block_till_done()

        assert switch.is_on(self.hass, self.switch_1.entity_id)
        assert switch.is_on(self.hass, self.switch_2.entity_id)
        assert switch.is_on(self.hass, self.switch_3.entity_id)

    def test_setup_two_platforms(self):
        """Test with bad configuration."""
        # Test if switch component returns 0 switches
        test_platform = getattr(self.hass.components, "test.switch")
        test_platform.init(True)

        mock_entity_platform(self.hass, "switch.test2", test_platform)
        test_platform.init(False)

        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {CONF_PLATFORM: "test"},
                f"{switch.DOMAIN} 2": {CONF_PLATFORM: "test2"},
            },
        )


async def test_switch_context(hass, hass_admin_user):
    """Test that switch context works."""
    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})

    await hass.async_block_till_done()

    state = hass.states.get("switch.ac")
    assert state is not None

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": state.entity_id},
        True,
        core.Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("switch.ac")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomSwitch(switch.SwitchDevice):
        pass

    CustomSwitch()
    assert "SwitchDevice is deprecated, modify CustomSwitch" in caplog.text
