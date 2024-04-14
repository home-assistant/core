"""The tests for the Template alarm control panel platform."""

import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback

TEMPLATE_NAME = "alarm_control_panel.test_template_panel"
PANEL_NAME = "alarm_control_panel.test"


@pytest.fixture
def service_calls(hass):
    """Track service call events for alarm_control_panel.test."""
    events = []
    entity_id = "alarm_control_panel.test"

    @callback
    def capture_events(event):
        if event.data[ATTR_DOMAIN] != ALARM_DOMAIN:
            return
        if event.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID] != [entity_id]:
            return
        events.append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, capture_events)

    return events


OPTIMISTIC_TEMPLATE_ALARM_CONFIG = {
    "arm_away": {
        "service": "alarm_control_panel.alarm_arm_away",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_home": {
        "service": "alarm_control_panel.alarm_arm_home",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_night": {
        "service": "alarm_control_panel.alarm_arm_night",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_vacation": {
        "service": "alarm_control_panel.alarm_arm_vacation",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_custom_bypass": {
        "service": "alarm_control_panel.alarm_arm_custom_bypass",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "disarm": {
        "service": "alarm_control_panel.alarm_disarm",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "trigger": {
        "service": "alarm_control_panel.alarm_trigger",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
}


TEMPLATE_ALARM_CONFIG = {
    "value_template": "{{ states('alarm_control_panel.test') }}",
    **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
}


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {"test_template_panel": TEMPLATE_ALARM_CONFIG},
            }
        },
    ],
)
async def test_template_state_text(hass: HomeAssistant, start_ha) -> None:
    """Test the state text of a template."""

    for set_state in [
        STATE_ALARM_ARMED_HOME,
        STATE_ALARM_ARMED_AWAY,
        STATE_ALARM_ARMED_NIGHT,
        STATE_ALARM_ARMED_VACATION,
        STATE_ALARM_ARMED_CUSTOM_BYPASS,
        STATE_ALARM_ARMING,
        STATE_ALARM_DISARMED,
        STATE_ALARM_PENDING,
        STATE_ALARM_TRIGGERED,
    ]:
        hass.states.async_set(PANEL_NAME, set_state)
        await hass.async_block_till_done()
        state = hass.states.get(TEMPLATE_NAME)
        assert state.state == set_state

    hass.states.async_set(PANEL_NAME, "invalid_state")
    await hass.async_block_till_done()
    state = hass.states.get(TEMPLATE_NAME)
    assert state.state == "unknown"


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {"test_template_panel": OPTIMISTIC_TEMPLATE_ALARM_CONFIG},
            }
        },
    ],
)
async def test_optimistic_states(hass: HomeAssistant, start_ha) -> None:
    """Test the optimistic state."""

    state = hass.states.get(TEMPLATE_NAME)
    await hass.async_block_till_done()
    assert state.state == "unknown"

    for service, set_state in [
        ("alarm_arm_away", STATE_ALARM_ARMED_AWAY),
        ("alarm_arm_home", STATE_ALARM_ARMED_HOME),
        ("alarm_arm_night", STATE_ALARM_ARMED_NIGHT),
        ("alarm_arm_vacation", STATE_ALARM_ARMED_VACATION),
        ("alarm_arm_custom_bypass", STATE_ALARM_ARMED_CUSTOM_BYPASS),
        ("alarm_disarm", STATE_ALARM_DISARMED),
        ("alarm_trigger", STATE_ALARM_TRIGGERED),
    ]:
        await hass.services.async_call(
            ALARM_DOMAIN, service, {"entity_id": TEMPLATE_NAME}, blocking=True
        )
        await hass.async_block_till_done()
        assert hass.states.get(TEMPLATE_NAME).state == set_state


@pytest.mark.parametrize(("count", "domain"), [(0, "alarm_control_panel")])
@pytest.mark.parametrize(
    ("config", "msg"),
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{% if blah %}",
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                        }
                    },
                }
            },
            "invalid template",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "bad name here": {
                            "value_template": "disarmed",
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                        }
                    },
                }
            },
            "invalid slug bad name",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "wibble": {"test_panel": "Invalid"},
                }
            },
            "'wibble' is an invalid option",
        ),
        (
            {
                "alarm_control_panel": {"platform": "template"},
            },
            "required key 'panels' not provided",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                            "code_format": "bad_format",
                        }
                    },
                }
            },
            "value must be one of ['no_code', 'number', 'text']",
        ),
    ],
)
async def test_template_syntax_error(
    hass: HomeAssistant, msg, start_ha, caplog_setup_text
) -> None:
    """Test templating syntax error."""
    assert len(hass.states.async_all("alarm_control_panel")) == 0
    assert (msg) in caplog_setup_text


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "name": "Template Alarm Panel",
                        "value_template": "disarmed",
                        **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                    }
                },
            }
        },
    ],
)
async def test_name(hass: HomeAssistant, start_ha) -> None:
    """Test the accessibility of the name attribute."""
    state = hass.states.get(TEMPLATE_NAME)
    assert state is not None
    assert state.attributes.get("friendly_name") == "Template Alarm Panel"


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {"test_template_panel": TEMPLATE_ALARM_CONFIG},
            }
        },
    ],
)
@pytest.mark.parametrize(
    "service",
    [
        "alarm_arm_home",
        "alarm_arm_away",
        "alarm_arm_night",
        "alarm_arm_vacation",
        "alarm_arm_custom_bypass",
        "alarm_disarm",
        "alarm_trigger",
    ],
)
async def test_actions(hass: HomeAssistant, service, start_ha, service_calls) -> None:
    """Test alarm actions."""
    await hass.services.async_call(
        ALARM_DOMAIN, service, {"entity_id": TEMPLATE_NAME}, blocking=True
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["service"] == service
    assert service_calls[0].data["service_data"]["code"] == TEMPLATE_NAME


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_alarm_control_panel_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_alarm_control_panel_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            },
        },
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha) -> None:
    """Test unique_id option only creates one alarm control panel per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    ("config", "code_format", "code_arm_required"),
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                        }
                    },
                }
            },
            "number",
            True,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "text",
                        }
                    },
                }
            },
            "text",
            True,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "no_code",
                            "code_arm_required": False,
                        }
                    },
                }
            },
            None,
            False,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "text",
                            "code_arm_required": False,
                        }
                    },
                }
            },
            "text",
            False,
        ),
    ],
)
async def test_code_config(
    hass: HomeAssistant, code_format, code_arm_required, start_ha
) -> None:
    """Test configuration options related to alarm code."""
    state = hass.states.get(TEMPLATE_NAME)
    assert state.attributes.get("code_format") == code_format
    assert state.attributes.get("code_arm_required") == code_arm_required
