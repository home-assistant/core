"""The tests for the Template alarm control panel platform."""
import logging

from homeassistant import setup
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)

from tests.common import async_mock_service
from tests.components.alarm_control_panel import common

_LOGGER = logging.getLogger(__name__)


async def test_template_state_text(hass):
    """Test the state text of a template."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_ARMED_HOME)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_ARMED_HOME

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_ARMED_AWAY)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_ARMED_AWAY

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_ARMED_NIGHT)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_ARMED_NIGHT

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_DISARMED)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_DISARMED

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_PENDING)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_PENDING

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_TRIGGERED)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == STATE_ALARM_TRIGGERED

    hass.states.async_set("alarm_control_panel.test", "invalid_state")
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == "unknown"


async def test_optimistic_states(hass):
    """Test the optimistic state."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == "unknown"

    await common.async_alarm_arm_away(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_arm_home(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_HOME

    await common.async_alarm_arm_night(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_NIGHT

    await common.async_alarm_disarm(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_DISARMED


async def test_no_action_scripts(hass):
    """Test no action scripts per state."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("alarm_control_panel.test", STATE_ALARM_ARMED_AWAY)
    await hass.async_block_till_done()

    await common.async_alarm_arm_away(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_arm_home(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_arm_night(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_AWAY

    await common.async_alarm_disarm(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    state = hass.states.get("alarm_control_panel.test_template_panel")
    await hass.async_block_till_done()
    assert state.state == STATE_ALARM_ARMED_AWAY


async def test_template_syntax_error(hass, caplog):
    """Test templating syntax error."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert ("invalid template") in caplog.text


async def test_invalid_name_does_not_create(hass, caplog):
    """Test invalid name."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert ("invalid slug bad name") in caplog.text


async def test_invalid_panel_does_not_create(hass, caplog):
    """Test invalid alarm control panel."""
    await setup.async_setup_component(
        hass,
        "alarm_control_panel",
        {
            "alarm_control_panel": {
                "platform": "template",
                "wibble": {"test_panel": "Invalid"},
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert ("[wibble] is an invalid option") in caplog.text


async def test_no_panels_does_not_create(hass, caplog):
    """Test if there are no panels -> no creation."""
    await setup.async_setup_component(
        hass, "alarm_control_panel", {"alarm_control_panel": {"platform": "template"}},
    )

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert ("required key not provided @ data['panels']") in caplog.text


async def test_name(hass):
    """Test the accessibility of the name attribute."""
    await setup.async_setup_component(
        hass,
        "alarm_control_panel",
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "name": "Template Alarm Panel",
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

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template Alarm Panel"


async def test_arm_home_action(hass):
    """Test arm home action."""
    await setup.async_setup_component(
        hass,
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

    await hass.async_start()
    await hass.async_block_till_done()

    service_calls = async_mock_service(hass, "test", "automation")

    await common.async_alarm_arm_home(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_arm_away_action(hass):
    """Test arm away action."""
    await setup.async_setup_component(
        hass,
        "alarm_control_panel",
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "value_template": "{{ states('alarm_control_panel.test') }}",
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_away": {"service": "test.automation"},
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

    await hass.async_start()
    await hass.async_block_till_done()

    service_calls = async_mock_service(hass, "test", "automation")

    await common.async_alarm_arm_away(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_arm_night_action(hass):
    """Test arm night action."""
    await setup.async_setup_component(
        hass,
        "alarm_control_panel",
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "value_template": "{{ states('alarm_control_panel.test') }}",
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_night": {"service": "test.automation"},
                        "arm_away": {
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

    await hass.async_start()
    await hass.async_block_till_done()

    service_calls = async_mock_service(hass, "test", "automation")

    await common.async_alarm_arm_night(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_disarm_action(hass):
    """Test disarm action."""
    await setup.async_setup_component(
        hass,
        "alarm_control_panel",
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "value_template": "{{ states('alarm_control_panel.test') }}",
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "disarm": {"service": "test.automation"},
                        "arm_away": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_night": {
                            "service": "alarm_control_panel.alarm_disarm",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    service_calls = async_mock_service(hass, "test", "automation")

    await common.async_alarm_disarm(
        hass, entity_id="alarm_control_panel.test_template_panel"
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
