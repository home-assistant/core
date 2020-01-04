"""The tests for the Template alarm control panel platform."""
import logging

from homeassistant import setup
from homeassistant.components.alarm_control_panel import (
    DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import callback

from tests.common import assert_setup_component, get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestTemplateAlarmControlPanel:
    """Test the Template alarm control panel."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        @callback
        def record_call(service):
            """Track function calls.."""
            self.calls.append(service)

        self.hass.services.register("test", "automation", record_call)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template_state_text(self):
        """Test the state text of a template."""
        with assert_setup_component(1, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "test_template_panel": {
                                "value_template": "{{ states('alarm_control_panel.test') }}",
                                "arm_away": {
                                    "service": "alarm_control_panel.alarm_arm_away",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_home": {
                                    "service": "alarm_control_panel.alarm_arm_home",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_night": {
                                    "service": "alarm_control_panel.alarm_arm_night",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "disarm": {
                                    "service": "alarm_control_panel.alarm_disarm",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set("alarm_control_panel.test", STATE_ALARM_ARMED_HOME)
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_ARMED_HOME

        state = self.hass.states.set("alarm_control_panel.test", STATE_ALARM_ARMED_AWAY)
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_ARMED_AWAY

        state = self.hass.states.set(
            "alarm_control_panel.test", STATE_ALARM_ARMED_NIGHT
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_ARMED_NIGHT

        state = self.hass.states.set("alarm_control_panel.test", STATE_ALARM_DISARMED)
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_DISARMED

    def test_optimistic_states(self):
        """Test the optimistic state."""
        with assert_setup_component(1, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "test_template_panel": {
                                "arm_away": {
                                    "service": "alarm_control_panel.alarm_arm_away",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_home": {
                                    "service": "alarm_control_panel.alarm_arm_home",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_night": {
                                    "service": "alarm_control_panel.alarm_arm_night",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "disarm": {
                                    "service": "alarm_control_panel.alarm_disarm",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == "unknown"

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_HOME

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_NIGHT,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_NIGHT

        self.hass.services.call(
            DOMAIN,
            "alarm_disarm",
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_DISARMED

    def test_no_action_scripts(self):
        """Test no action scripts per state."""
        with assert_setup_component(1, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "test_template_panel": {
                                "value_template": "{{ states('alarm_control_panel.test') }}",
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            "alarm_control_panel.test_template_panel", STATE_ALARM_ARMED_AWAY
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_NIGHT,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            "alarm_disarm",
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()
        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        self.hass.block_till_done()
        assert state.state == STATE_ALARM_ARMED_AWAY

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "test_template_panel": {
                                "value_template": "{% if blah %}",
                                "arm_away": {
                                    "service": "alarm_control_panel.alarm_arm_away",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_home": {
                                    "service": "alarm_control_panel.alarm_arm_home",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_night": {
                                    "service": "alarm_control_panel.alarm_arm_night",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "disarm": {
                                    "service": "alarm_control_panel.alarm_disarm",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "bad name here": {
                                "value_template": "{{ disarmed }}",
                                "arm_away": {
                                    "service": "alarm_control_panel.alarm_arm_away",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_home": {
                                    "service": "alarm_control_panel.alarm_arm_home",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_night": {
                                    "service": "alarm_control_panel.alarm_arm_night",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "disarm": {
                                    "service": "alarm_control_panel.alarm_disarm",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_panel_does_not_create(self):
        """Test invalid alarm control panel."""
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "wibble": {"test_panel": "Invalid"},
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_panels_does_not_create(self):
        """Test if there are no panels -> no creation."""
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {"alarm_control_panel": {"platform": "template"}},
            )

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_disarm_action(self):
        """Test disarm action."""
        assert setup.setup_component(
            self.hass,
            "alarm_control_panel",
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            "alarm_control_panel.test_template_panel", STATE_ALARM_ARMED_AWAY
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_ARMED_AWAY

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_DISARM,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_arm_away_action(self):
        """Test disarm action."""
        assert setup.setup_component(
            self.hass,
            "alarm_control_panel",
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_away": {"service": "test.automation"},
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
        )

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            "alarm_control_panel.test_template_panel", STATE_ALARM_DISARMED
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_DISARMED

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_arm_night_action(self):
        """Test disarm action."""
        assert setup.setup_component(
            self.hass,
            "alarm_control_panel",
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {"service": "test.automation"},
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
        )

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            "alarm_control_panel.test_template_panel", STATE_ALARM_DISARMED
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_DISARMED

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_NIGHT,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_arm_home_action(self):
        """Test disarm action."""
        assert setup.setup_component(
            self.hass,
            "alarm_control_panel",
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {"service": "test.automation"},
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
        )

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            "alarm_control_panel.test_template_panel", STATE_ALARM_DISARMED
        )
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state.state == STATE_ALARM_DISARMED

        self.hass.services.call(
            DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {"entity_id": "alarm_control_panel.test_template_panel"},
        )
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_friendly_name(self):
        """Test the accessibility of the friendly_name attribute."""
        with assert_setup_component(1, "alarm_control_panel"):
            assert setup.setup_component(
                self.hass,
                "alarm_control_panel",
                {
                    "alarm_control_panel": {
                        "platform": "template",
                        "panels": {
                            "test_template_panel": {
                                "friendly_name": "Template Alarm Panel",
                                "value_template": "{{ disarmed }}",
                                "arm_away": {
                                    "service": "alarm_control_panel.alarm_arm_away",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_home": {
                                    "service": "alarm_control_panel.alarm_arm_home",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "arm_night": {
                                    "service": "alarm_control_panel.alarm_arm_night",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                                "disarm": {
                                    "service": "alarm_control_panel.alarm_disarm",
                                    "entity_id": "alarm_control_panel.test",
                                    "data": {"code": "1234"},
                                },
                            }
                        },
                    }
                },
            )

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("alarm_control_panel.test_template_panel")
        assert state is not None

        assert state.attributes.get("friendly_name") == "Template Alarm Panel"
