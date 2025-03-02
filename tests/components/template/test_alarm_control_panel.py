"""The tests for the Template alarm control panel platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component, mock_restore_cache

TEMPLATE_NAME = "alarm_control_panel.test_template_panel"
PANEL_NAME = "alarm_control_panel.test"


@pytest.fixture
def call_service_events(hass: HomeAssistant) -> list[Event]:
    """Track service call events for alarm_control_panel.test."""
    events: list[Event] = []
    entity_id = "alarm_control_panel.test"

    @callback
    def capture_events(event: Event) -> None:
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
@pytest.mark.usefixtures("start_ha")
async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""

    for set_state in (
        AlarmControlPanelState.ARMED_HOME,
        AlarmControlPanelState.ARMED_AWAY,
        AlarmControlPanelState.ARMED_NIGHT,
        AlarmControlPanelState.ARMED_VACATION,
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        AlarmControlPanelState.ARMING,
        AlarmControlPanelState.DISARMED,
        AlarmControlPanelState.PENDING,
        AlarmControlPanelState.TRIGGERED,
    ):
        hass.states.async_set(PANEL_NAME, set_state)
        await hass.async_block_till_done()
        state = hass.states.get(TEMPLATE_NAME)
        assert state.state == set_state

    hass.states.async_set(PANEL_NAME, "invalid_state")
    await hass.async_block_till_done()
    state = hass.states.get(TEMPLATE_NAME)
    assert state.state == "unknown"


async def test_setup_config_entry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the config flow."""
    value_template = "{{ states('alarm_control_panel.one') }}"

    hass.states.async_set("alarm_control_panel.one", "armed_away", {})

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "value_template": value_template,
            "template_type": "alarm_control_panel",
            "code_arm_required": True,
            "code_format": "number",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.my_template")
    assert state is not None
    assert state == snapshot

    hass.states.async_set("alarm_control_panel.one", "disarmed", {})
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.my_template")
    assert state.state == AlarmControlPanelState.DISARMED


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
@pytest.mark.usefixtures("start_ha")
async def test_optimistic_states(hass: HomeAssistant) -> None:
    """Test the optimistic state."""

    state = hass.states.get(TEMPLATE_NAME)
    await hass.async_block_till_done()
    assert state.state == "unknown"

    for service, set_state in (
        ("alarm_arm_away", AlarmControlPanelState.ARMED_AWAY),
        ("alarm_arm_home", AlarmControlPanelState.ARMED_HOME),
        ("alarm_arm_night", AlarmControlPanelState.ARMED_NIGHT),
        ("alarm_arm_vacation", AlarmControlPanelState.ARMED_VACATION),
        ("alarm_arm_custom_bypass", AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        ("alarm_disarm", AlarmControlPanelState.DISARMED),
        ("alarm_trigger", AlarmControlPanelState.TRIGGERED),
    ):
        await hass.services.async_call(
            ALARM_DOMAIN,
            service,
            {"entity_id": TEMPLATE_NAME, "code": "1234"},
            blocking=True,
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
@pytest.mark.usefixtures("start_ha")
async def test_template_syntax_error(
    hass: HomeAssistant, msg, caplog_setup_text
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
                        "name": '{{ "Template Alarm Panel" }}',
                        "value_template": "disarmed",
                        **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                    }
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_name(hass: HomeAssistant) -> None:
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
@pytest.mark.usefixtures("start_ha")
async def test_actions(
    hass: HomeAssistant, service, call_service_events: list[Event]
) -> None:
    """Test alarm actions."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {"entity_id": TEMPLATE_NAME, "code": "1234"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(call_service_events) == 1
    assert call_service_events[0].data["service"] == service
    assert call_service_events[0].data["service_data"]["code"] == TEMPLATE_NAME


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
@pytest.mark.usefixtures("start_ha")
async def test_unique_id(hass: HomeAssistant) -> None:
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
@pytest.mark.usefixtures("start_ha")
async def test_code_config(hass: HomeAssistant, code_format, code_arm_required) -> None:
    """Test configuration options related to alarm code."""
    state = hass.states.get(TEMPLATE_NAME)
    assert state.attributes.get("code_format") == code_format
    assert state.attributes.get("code_arm_required") == code_arm_required


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
    ("restored_state", "initial_state"),
    [
        (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (
            AlarmControlPanelState.ARMED_VACATION,
            AlarmControlPanelState.ARMED_VACATION,
        ),
        (AlarmControlPanelState.ARMING, AlarmControlPanelState.ARMING),
        (AlarmControlPanelState.DISARMED, AlarmControlPanelState.DISARMED),
        (AlarmControlPanelState.PENDING, AlarmControlPanelState.PENDING),
        (
            AlarmControlPanelState.TRIGGERED,
            AlarmControlPanelState.TRIGGERED,
        ),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        (STATE_UNKNOWN, STATE_UNKNOWN),
        ("faulty_state", STATE_UNKNOWN),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    count,
    domain,
    config,
    restored_state,
    initial_state,
) -> None:
    """Test restoring template alarm control panel."""

    fake_state = State(
        "alarm_control_panel.test_template_panel",
        restored_state,
        {},
    )
    mock_restore_cache(hass, (fake_state,))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

        await hass.async_block_till_done()

        await hass.async_start()
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == initial_state


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for button template."""

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "value_template": "disarmed",
            "template_type": "alarm_control_panel",
            "code_arm_required": True,
            "code_format": "number",
            "device_id": device_entry.id,
        },
        title="My template",
    )

    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("alarm_control_panel.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id
