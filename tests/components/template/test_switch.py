"""The tests for the  Template switch platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import switch, template
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_component,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

TEST_OBJECT_ID = "test_template_switch"
TEST_ENTITY_ID = f"switch.{TEST_OBJECT_ID}"
SWITCH_ACTIONS = {
    "turn_on": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_on",
            "caller": "{{ this.entity_id }}",
        },
    },
    "turn_off": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_off",
            "caller": "{{ this.entity_id }}",
        },
    },
}
NAMED_SWITCH_ACTIONS = {
    **SWITCH_ACTIONS,
    "name": TEST_OBJECT_ID,
}


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ True }}",
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ True }}",
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_setup(hass: HomeAssistant) -> None:
    """Test template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.name == TEST_OBJECT_ID
    assert state.state == STATE_ON


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    hass.states.async_set(
        "switch.one",
        "on",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('switch.one') }}",
            "template_type": SWITCH_DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.my_template")
    assert state is not None
    assert state == snapshot


async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    with assert_setup_component(1, "template"):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ states.switch.test_state.state }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ 1 == 1 }}", STATE_ON),
        ("{{ 1 == 2 }}", STATE_OFF),
    ],
)
async def test_template_state_boolean(
    hass: HomeAssistant, template: str, expected: str
) -> None:
    """Test the setting of the state with boolean on."""
    with assert_setup_component(1, "template"):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": template,
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected


@pytest.mark.parametrize(
    ("field", "attribute", "expected"),
    [
        (
            "icon",
            "icon",
            "mdi:check",
        ),
        (
            "picture",
            "entity_picture",
            "/local/switch.png",
        ),
    ],
)
async def test_icon_and_picture_template(
    hass: HomeAssistant, field: str, attribute: str, expected: str
) -> None:
    """Test icon template."""
    with assert_setup_component(1, "template"):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ states.switch.test_state.state }}",
                        field: (
                            "{% if states.switch.test_state.state %}"
                            f"{expected}"
                            "{% endif %}"
                        ),
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(attribute) == ""

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes[attribute] == expected


async def test_template_syntax_error(hass: HomeAssistant) -> None:
    """Test templating syntax error."""
    with assert_setup_component(0, "template"):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{% if rubbish %}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_invalid_name_does_not_create(hass: HomeAssistant) -> None:
    """Test invalid name."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "test INVALID switch": {
                            **NAMED_SWITCH_ACTIONS,
                            "value_template": "{{ rubbish }",
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_invalid_switch_does_not_create(hass: HomeAssistant) -> None:
    """Test invalid switch."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {TEST_OBJECT_ID: "Invalid"},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_no_switches_does_not_create(hass: HomeAssistant) -> None:
    """Test if there are no switches no creation."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass, "switch", {"switch": {"platform": "template"}}
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_missing_on_does_not_create(hass: HomeAssistant) -> None:
    """Test missing on."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            "value_template": "{{ states.switch.test_state.state }}",
                            "not_on": {
                                "service": "switch.turn_on",
                                "entity_id": "switch.test_state",
                            },
                            "turn_off": {
                                "service": "switch.turn_off",
                                "entity_id": "switch.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_missing_off_does_not_create(hass: HomeAssistant) -> None:
    """Test missing off."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            "value_template": "{{ states.switch.test_state.state }}",
                            "turn_on": {
                                "service": "switch.turn_on",
                                "entity_id": "switch.test_state",
                            },
                            "not_off": {
                                "service": "switch.turn_off",
                                "entity_id": "switch.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_on_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test on action."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                        "value_template": "{{ states.switch.test_state.state }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


async def test_on_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test on action in optimistic mode."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(TEST_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


async def test_off_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test off action."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                        "value_template": "{{ states.switch.test_state.state }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


async def test_off_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test off action in optimistic mode."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(TEST_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test state restoration."""
    mock_restore_cache(
        hass,
        (
            State("switch.s1", STATE_ON),
            State("switch.s2", STATE_OFF),
        ),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "s1": {
                        **SWITCH_ACTIONS,
                    },
                    "s2": {
                        **SWITCH_ACTIONS,
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.s1")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("switch.s2")
    assert state
    assert state.state == STATE_OFF


async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                        "value_template": "{{ 1 == 1 }}",
                        "availability_template": (
                            "{{ is_state('availability_state.state', 'on') }}"
                        ),
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    TEST_OBJECT_ID: {
                        **SWITCH_ACTIONS,
                        "value_template": "{{ true }}",
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog.text


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one switch per id."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch_01": {
                        **SWITCH_ACTIONS,
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_switch_02": {
                        **SWITCH_ACTIONS,
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("switch")) == 1


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for Template."""

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
            "state": "{{ true }}",
            "template_type": "switch",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("switch.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(("count", "domain"), [(2, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "switches": {
                        "hello": {
                            **SWITCH_ACTIONS,
                            "friendly_name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "value_template": "{{ trigger.event.data.beer == 2 }}",
                            "entity_picture_template": "{{ '/local/dogs.png' }}",
                            "icon_template": "{{ 'mdi:pirate' }}",
                        }
                    },
                    "switch": [
                        {
                            **SWITCH_ACTIONS,
                            "name": "via list",
                            "unique_id": "via_list-id",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                            "picture": "{{ '/local/dogs2.png' if trigger.event.data.uno_mas is defined else '/local/dogs.png' }}",
                            "icon": "{{ 'mdi:pirate' }}",
                        },
                    ],
                },
                {
                    "trigger": [],
                    "switches": {
                        "bare_minimum": {**SWITCH_ACTIONS},
                    },
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test trigger entity works."""
    await hass.async_block_till_done()
    state = hass.states.get("switch.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("switch.via_list")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("switch.bare_minimum")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hello_name")
    assert state.state == STATE_ON
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.context is context

    state = hass.states.get("switch.via_list")
    assert state.state == STATE_ON
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.context is context

    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.entities["switch.hello_name"].unique_id
        == "listening-test-event-hello_name-id"
    )
    assert (
        entity_registry.entities["switch.via_list"].unique_id
        == "listening-test-event-via_list-id"
    )

    # Even if state itself didn't change, attributes might have changed
    hass.bus.async_fire("test_event", {"beer": 2, "uno_mas": "si"})
    await hass.async_block_till_done()
    state = hass.states.get("switch.via_list")
    assert state.attributes.get("entity_picture") == "/local/dogs2.png"
    assert state.state == STATE_ON


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "switch": [
                        {
                            **SWITCH_ACTIONS,
                            "name": "via list",
                            "unique_id": "via_list-id",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                        },
                        {
                            **SWITCH_ACTIONS,
                            "name": "optimistic",
                            "unique_id": "optimistic-id",
                            "picture": "{{ '/local/a.png' if trigger.event.data.beer == 2 else '/local/b.png' }}",
                        },
                        {
                            **SWITCH_ACTIONS,
                            "name": "unavailable",
                            "unique_id": "unavailable-id",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                            "availability": "{{ trigger.event.data.beer == 2 }}",
                        },
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_optimistic_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls: list[ServiceCall]
) -> None:
    """Test trigger entity works."""
    await hass.async_block_till_done()

    state = hass.states.get("switch.via_list")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("switch.optimistic")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("switch.unavailable")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("switch.via_list")
    assert state.state == STATE_ON
    assert state.context is context

    # Even if an event triggered, an optimistic switch should not change
    state = hass.states.get("switch.optimistic")
    assert state is not None
    # Templated attributes should change
    assert state.attributes.get("entity_picture") == "/local/a.png"
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("switch.unavailable")
    assert state.state == STATE_ON
    assert state.context is context

    assert len(entity_registry.entities) == 3
    assert (
        entity_registry.entities["switch.via_list"].unique_id
        == "listening-test-event-via_list-id"
    )
    assert (
        entity_registry.entities["switch.optimistic"].unique_id
        == "listening-test-event-optimistic-id"
    )
    assert (
        entity_registry.entities["switch.unavailable"].unique_id
        == "listening-test-event-unavailable-id"
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.optimistic"},
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "switch.optimistic"

    state = hass.states.get("switch.optimistic")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.optimistic"},
        blocking=True,
    )
    assert len(calls) == 2
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == "switch.optimistic"

    state = hass.states.get("switch.optimistic")
    assert state is not None
    assert state.state == STATE_OFF

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("switch.optimistic")
    assert state is not None
    assert state.attributes.get("entity_picture") == "/local/b.png"
    assert state.state == STATE_OFF

    state = hass.states.get("switch.unavailable")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "switch": [
                    {
                        **SWITCH_ACTIONS,
                        "name": "test",
                        "unique_id": "test",
                        "state": "{{ trigger.event.data.beer == 2 }}",
                        "icon": "{{ 'mdi:a' if trigger.event.data.beer == 2 else 'mdi:b' }}",
                        "picture": "{{ '/local/a.png' if trigger.event.data.beer == 2 else '/local/b.png' }}",
                    },
                ],
            }
        },
    ],
)
@pytest.mark.parametrize(
    ("restored_state", "initial_state", "initial_attributes"),
    [
        (STATE_ON, STATE_ON, ["entity_picture", "icon"]),
        (STATE_OFF, STATE_OFF, ["entity_picture", "icon", "plus_one"]),
        (STATE_UNAVAILABLE, STATE_UNKNOWN, []),
        (STATE_UNKNOWN, STATE_UNKNOWN, []),
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    count,
    domain,
    config,
    restored_state,
    initial_state,
    initial_attributes,
) -> None:
    """Test restoring trigger template binary sensor."""

    restored_attributes = {
        "entity_picture": "/local/c.png",
        "icon": "mdi:c",
    }

    fake_state = State(
        "switch.test",
        restored_state,
        restored_attributes,
    )
    mock_restore_cache_with_extra_data(hass, ((fake_state, {}),))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state.state == initial_state
    for attr, value in restored_attributes.items():
        if attr in initial_attributes:
            assert state.attributes[attr] == value
        else:
            assert attr not in state.attributes
    assert "another" not in state.attributes

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    assert state.attributes["icon"] == "mdi:a"
    assert state.attributes["entity_picture"] == "/local/a.png"
