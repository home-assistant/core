"""The tests for the Template lock platform."""
import logging

from homeassistant import setup
from homeassistant.components import lock
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import callback

from tests.common import assert_setup_component, get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestTemplateLock:
    """Test the Template lock."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        @callback
        def record_call(service):
            """Track function calls."""
            self.calls.append(service)

        self.hass.services.register("test", "automation", record_call)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template_state(self):
        """Test template."""
        with assert_setup_component(1, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "name": "Test template lock",
                        "value_template": "{{ states.switch.test_state.state }}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("lock.test_template_lock")
        assert state.state == lock.STATE_LOCKED

        self.hass.states.set("switch.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("lock.test_template_lock")
        assert state.state == lock.STATE_UNLOCKED

    def test_template_state_boolean_on(self):
        """Test the setting of the state with boolean on."""
        with assert_setup_component(1, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "value_template": "{{ 1 == 1 }}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_LOCKED

    def test_template_state_boolean_off(self):
        """Test the setting of the state with off."""
        with assert_setup_component(1, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "value_template": "{{ 1 == 2 }}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_UNLOCKED

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "value_template": "{% if rubbish %}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "switch": {
                        "platform": "lock",
                        "name": "{{%}",
                        "value_template": "{{ rubbish }",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_lock_does_not_create(self):
        """Test invalid lock."""
        with assert_setup_component(0, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {"lock": {"platform": "template", "value_template": "Invalid"}},
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        with assert_setup_component(0, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "not_value_template": "{{ states.switch.test_state.state }}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_template_match_all(self, caplog):
        """Test that we do not allow locks that match on all."""
        with assert_setup_component(1, "lock"):
            assert setup.setup_component(
                self.hass,
                "lock",
                {
                    "lock": {
                        "platform": "template",
                        "value_template": "{{ 1 + 1 }}",
                        "lock": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "unlock": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_UNLOCKED

        assert (
            "Template lock 'Template Lock' has no entity ids configured to track "
            "nor were we able to extract the entities to track from the value "
            "template(s). This entity will only be able to be updated manually"
        ) in caplog.text

        self.hass.states.set("lock.template_lock", lock.STATE_LOCKED)
        self.hass.block_till_done()
        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_LOCKED

    def test_lock_action(self):
        """Test lock action."""
        assert setup.setup_component(
            self.hass,
            "lock",
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ states.switch.test_state.state }}",
                    "lock": {"service": "test.automation"},
                    "unlock": {
                        "service": "switch.turn_off",
                        "entity_id": "switch.test_state",
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("switch.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_UNLOCKED

        self.hass.services.call(
            lock.DOMAIN, lock.SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_unlock_action(self):
        """Test unlock action."""
        assert setup.setup_component(
            self.hass,
            "lock",
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ states.switch.test_state.state }}",
                    "lock": {
                        "service": "switch.turn_on",
                        "entity_id": "switch.test_state",
                    },
                    "unlock": {"service": "test.automation"},
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("lock.template_lock")
        assert state.state == lock.STATE_LOCKED

        self.hass.services.call(
            lock.DOMAIN, lock.SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1


async def test_available_template_with_entities(hass):
    """Test availability templates with values from other entities."""

    await setup.async_setup_component(
        hass,
        "lock",
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states('switch.test_state') }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
                "availability_template": "{{ is_state('availability_state.state', 'on') }}",
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # When template returns true..
    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("lock.template_lock").state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        "lock",
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ 1 + 1 }}",
                "availability_template": "{{ x - 12 }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text
