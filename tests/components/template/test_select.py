"""The tests for the Template select platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components.input_select import (
    ATTR_OPTION as INPUT_SELECT_ATTR_OPTION,
    ATTR_OPTIONS as INPUT_SELECT_ATTR_OPTIONS,
    DOMAIN as INPUT_SELECT_DOMAIN,
    SERVICE_SELECT_OPTION as INPUT_SELECT_SERVICE_SELECT_OPTION,
    SERVICE_SET_OPTIONS,
)
from homeassistant.components.select import (
    ATTR_OPTION as SELECT_ATTR_OPTION,
    ATTR_OPTIONS as SELECT_ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION as SELECT_SERVICE_SELECT_OPTION,
)
from homeassistant.components.template import DOMAIN
from homeassistant.const import ATTR_ICON, CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, assert_setup_component, async_capture_events

_TEST_SELECT = "select.template_select"
# Represent for select's current_option
_OPTION_INPUT_SELECT = "input_select.option"


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "select",
            "state": "{{ 'on' }}",
            "options": "{{ ['off', 'on', 'auto'] }}",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_template")
    assert state is not None
    assert state == snapshot


async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "select": {
                        "state": "{{ 'a' }}",
                        "select_option": {"service": "script.select_option"},
                        "options": "{{ ['a', 'b'] }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, "a", ["a", "b"])


async def test_multiple_configs(hass: HomeAssistant) -> None:
    """Test: multiple select entities get created."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "select": [
                        {
                            "state": "{{ 'a' }}",
                            "select_option": {"service": "script.select_option"},
                            "options": "{{ ['a', 'b'] }}",
                        },
                        {
                            "state": "{{ 'a' }}",
                            "select_option": {"service": "script.select_option"},
                            "options": "{{ ['a', 'b'] }}",
                        },
                    ]
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, "a", ["a", "b"])
    _verify(hass, "a", ["a", "b"], f"{_TEST_SELECT}_2")


async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "select": {
                        "select_option": {"service": "script.select_option"},
                        "options": "{{ ['a', 'b'] }}",
                    }
                }
            },
        )

    with assert_setup_component(0, "select"):
        assert await setup.async_setup_component(
            hass,
            "select",
            {
                "template": {
                    "select": {
                        "state": "{{ 'a' }}",
                        "select_option": {"service": "script.select_option"},
                    }
                }
            },
        )

    with assert_setup_component(0, "select"):
        assert await setup.async_setup_component(
            hass,
            "select",
            {
                "template": {
                    "select": {
                        "state": "{{ 'a' }}",
                        "options": "{{ ['a', 'b'] }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("select") == []


async def test_templates_with_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls: list[ServiceCall]
) -> None:
    """Test templates with values from other entities."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "option": {
                        "options": ["a", "b"],
                        "initial": "a",
                        "name": "Option",
                    },
                }
            },
        )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "b",
                    "select": {
                        "state": f"{{{{ states('{_OPTION_INPUT_SELECT}') }}}}",
                        "options": f"{{{{ state_attr('{_OPTION_INPUT_SELECT}', '{INPUT_SELECT_ATTR_OPTIONS}') }}}}",
                        "select_option": [
                            {
                                "service": "input_select.select_option",
                                "data_template": {
                                    "entity_id": _OPTION_INPUT_SELECT,
                                    "option": "{{ option }}",
                                },
                            },
                            {
                                "service": "test.automation",
                                "data_template": {
                                    "action": "select_option",
                                    "caller": "{{ this.entity_id }}",
                                    "option": "{{ option }}",
                                },
                            },
                        ],
                        "optimistic": True,
                        "unique_id": "a",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    entry = entity_registry.async_get(_TEST_SELECT)
    assert entry
    assert entry.unique_id == "b-a"

    _verify(hass, "a", ["a", "b"])

    await hass.services.async_call(
        INPUT_SELECT_DOMAIN,
        INPUT_SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: _OPTION_INPUT_SELECT, INPUT_SELECT_ATTR_OPTION: "b"},
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, "b", ["a", "b"])

    await hass.services.async_call(
        INPUT_SELECT_DOMAIN,
        SERVICE_SET_OPTIONS,
        {
            CONF_ENTITY_ID: _OPTION_INPUT_SELECT,
            INPUT_SELECT_ATTR_OPTIONS: ["a", "b", "c"],
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, "b", ["a", "b", "c"])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: _TEST_SELECT, SELECT_ATTR_OPTION: "c"},
        blocking=True,
    )
    _verify(hass, "c", ["a", "b", "c"])

    # Check this variable can be used in set_value script
    assert len(calls) == 1
    assert calls[-1].data["action"] == "select_option"
    assert calls[-1].data["caller"] == _TEST_SELECT
    assert calls[-1].data["option"] == "c"


async def test_trigger_select(hass: HomeAssistant) -> None:
    """Test trigger based template select."""
    events = async_capture_events(hass, "test_number_event")
    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "select": [
                        {
                            "name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "state": "{{ trigger.event.data.beer }}",
                            "options": "{{ trigger.event.data.beers }}",
                            "select_option": {"event": "test_number_event"},
                            "optimistic": True,
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("select.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire(
        "test_event", {"beer": "duff", "beers": ["duff", "alamo"]}, context=context
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.hello_name")
    assert state is not None
    assert state.state == "duff"
    assert state.attributes["options"] == ["duff", "alamo"]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: "select.hello_name", SELECT_ATTR_OPTION: "alamo"},
        blocking=True,
    )
    assert len(events) == 1
    assert events[0].event_type == "test_number_event"


def _verify(
    hass: HomeAssistant,
    expected_current_option: str,
    expected_options: list[str],
    entity_name: str = _TEST_SELECT,
) -> None:
    """Verify select's state."""
    state = hass.states.get(entity_name)
    attributes = state.attributes
    assert state.state == str(expected_current_option)
    assert attributes.get(SELECT_ATTR_OPTIONS) == expected_options


async def test_template_icon_with_entities(hass: HomeAssistant) -> None:
    """Test templates with values from other entities."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "option": {
                        "options": ["a", "b"],
                        "initial": "a",
                        "name": "Option",
                    },
                }
            },
        )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "b",
                    "select": {
                        "state": f"{{{{ states('{_OPTION_INPUT_SELECT}') }}}}",
                        "options": f"{{{{ state_attr('{_OPTION_INPUT_SELECT}', '{INPUT_SELECT_ATTR_OPTIONS}') }}}}",
                        "select_option": {
                            "service": "input_select.select_option",
                            "data": {
                                "entity_id": _OPTION_INPUT_SELECT,
                                "option": "{{ option }}",
                            },
                        },
                        "optimistic": True,
                        "unique_id": "a",
                        "icon": f"{{% if (states('{_OPTION_INPUT_SELECT}') == 'a') %}}mdi:greater{{% else %}}mdi:less{{% endif %}}",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "a"
    assert state.attributes[ATTR_ICON] == "mdi:greater"

    await hass.services.async_call(
        INPUT_SELECT_DOMAIN,
        INPUT_SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: _OPTION_INPUT_SELECT, INPUT_SELECT_ATTR_OPTION: "b"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "b"
    assert state.attributes[ATTR_ICON] == "mdi:less"


async def test_template_icon_with_trigger(hass: HomeAssistant) -> None:
    """Test trigger based template select."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "option": {
                        "options": ["a", "b"],
                        "initial": "a",
                        "name": "Option",
                    },
                }
            },
        )

    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": {
                "trigger": {"platform": "state", "entity_id": _OPTION_INPUT_SELECT},
                "select": {
                    "unique_id": "b",
                    "state": "{{ trigger.to_state.state }}",
                    "options": f"{{{{ state_attr('{_OPTION_INPUT_SELECT}', '{INPUT_SELECT_ATTR_OPTIONS}') }}}}",
                    "select_option": {
                        "service": "input_select.select_option",
                        "data": {
                            "entity_id": _OPTION_INPUT_SELECT,
                            "option": "{{ option }}",
                        },
                    },
                    "optimistic": True,
                    "icon": "{% if (trigger.to_state.state or '') == 'a' %}mdi:greater{% else %}mdi:less{% endif %}",
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        INPUT_SELECT_DOMAIN,
        INPUT_SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: _OPTION_INPUT_SELECT, INPUT_SELECT_ATTR_OPTION: "b"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state is not None
    assert state.state == "b"
    assert state.attributes[ATTR_ICON] == "mdi:less"

    await hass.services.async_call(
        INPUT_SELECT_DOMAIN,
        INPUT_SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: _OPTION_INPUT_SELECT, INPUT_SELECT_ATTR_OPTION: "a"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "a"
    assert state.attributes[ATTR_ICON] == "mdi:greater"


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for select template."""

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
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "select",
            "state": "{{ 'on' }}",
            "options": "{{ ['off', 'on', 'auto'] }}",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("select.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id
