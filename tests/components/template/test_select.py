"""The tests for the Template select platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import select, template
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
from homeassistant.components.template.const import CONF_PICTURE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    CONF_ENTITY_ID,
    CONF_ICON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle, async_get_flow_preview_state

from tests.common import MockConfigEntry, assert_setup_component, async_capture_events
from tests.conftest import WebSocketGenerator

_TEST_OBJECT_ID = "template_select"
_TEST_SELECT = f"select.{_TEST_OBJECT_ID}"
# Represent for select's current_option
_OPTION_INPUT_SELECT = "input_select.option"
TEST_STATE_ENTITY_ID = "select.test_state"
TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.test_availability"
TEST_STATE_TRIGGER = {
    "trigger": {
        "trigger": "state",
        "entity_id": [
            _OPTION_INPUT_SELECT,
            TEST_STATE_ENTITY_ID,
            TEST_AVAILABILITY_ENTITY_ID,
        ],
    },
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [
        {"event": "action_event", "event_data": {"what": "{{ triggering_entity }}"}}
    ],
}

TEST_OPTIONS = {
    "state": "test",
    "options": "{{ ['test', 'yes', 'no'] }}",
    "select_option": [],
}


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, select_config: dict[str, Any]
) -> None:
    """Do setup of select integration via new format."""
    config = {"template": {"select": select_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant, count: int, select_config: dict[str, Any]
) -> None:
    """Do setup of select integration via trigger format."""
    config = {"template": {**TEST_STATE_TRIGGER, "select": select_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def setup_select(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    select_config: dict[str, Any],
) -> None:
    """Do setup of select integration."""
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass, count, {"name": _TEST_OBJECT_ID, **select_config}
        )
    if style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass, count, {"name": _TEST_OBJECT_ID, **select_config}
        )


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
    action_events = async_capture_events(hass, "action_event")
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
                    "variables": {"beer": "{{ trigger.event.data.beer }}"},
                    "action": [
                        {"event": "action_event", "event_data": {"beer": "{{ beer }}"}}
                    ],
                    "select": [
                        {
                            "name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "state": "{{ trigger.event.data.beer }}",
                            "options": "{{ trigger.event.data.beers }}",
                            "select_option": {
                                "event": "test_number_event",
                                "event_data": {
                                    "entity_id": "{{ this.entity_id }}",
                                    "beer": "{{ beer }}",
                                },
                            },
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

    assert len(action_events) == 1
    assert action_events[0].event_type == "action_event"
    beer = action_events[0].data.get("beer")
    assert beer is not None
    assert beer == "duff"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: "select.hello_name", SELECT_ATTR_OPTION: "alamo"},
        blocking=True,
    )
    assert len(events) == 1
    assert events[0].event_type == "test_number_event"
    entity_id = events[0].data.get("entity_id")
    assert entity_id is not None
    assert entity_id == "select.hello_name"

    beer = events[0].data.get("beer")
    assert beer is not None
    assert beer == "duff"


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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "initial_expected_state"),
    [(ConfigurationStyle.MODERN, ""), (ConfigurationStyle.TRIGGER, None)],
)
@pytest.mark.parametrize(
    ("select_config", "attribute", "expected"),
    [
        (
            {
                **TEST_OPTIONS,
                CONF_ICON: "{% if states.select.test_state.state == 'yes' %}mdi:check{% endif %}",
            },
            ATTR_ICON,
            "mdi:check",
        ),
        (
            {
                **TEST_OPTIONS,
                CONF_PICTURE: "{% if states.select.test_state.state == 'yes' %}check.jpg{% endif %}",
            },
            ATTR_ENTITY_PICTURE,
            "check.jpg",
        ),
    ],
)
@pytest.mark.usefixtures("setup_select")
async def test_templated_optional_config(
    hass: HomeAssistant,
    attribute: str,
    expected: str,
    initial_expected_state: str | None,
) -> None:
    """Test optional config templates."""
    state = hass.states.get(_TEST_SELECT)
    assert state.attributes.get(attribute) == initial_expected_state

    state = hass.states.async_set(TEST_STATE_ENTITY_ID, "yes")
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)

    assert state.attributes[attribute] == expected


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


@pytest.mark.parametrize(
    ("count", "select_config"),
    [
        (
            1,
            {
                "state": "{{ 'b' }}",
                "select_option": [],
                "options": "{{ ['a', 'b'] }}",
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.MODERN,
    ],
)
async def test_empty_action_config(hass: HomeAssistant, setup_select) -> None:
    """Test configuration with empty script."""
    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _TEST_SELECT, "option": "a"},
        blocking=True,
    )

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "a"


@pytest.mark.parametrize(
    ("count", "select_config"),
    [
        (
            1,
            {
                "options": "{{ ['test', 'yes', 'no'] }}",
                "select_option": [],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_select")
async def test_optimistic(hass: HomeAssistant) -> None:
    """Test configuration with optimistic state."""

    state = hass.states.get(_TEST_SELECT)
    assert state.state == STATE_UNKNOWN

    # Ensure Trigger template entities update.
    hass.states.async_set(TEST_STATE_ENTITY_ID, "anything")
    await hass.async_block_till_done()

    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _TEST_SELECT, "option": "test"},
        blocking=True,
    )

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "test"

    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _TEST_SELECT, "option": "yes"},
        blocking=True,
    )

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "yes"


@pytest.mark.parametrize(
    ("count", "select_config"),
    [
        (
            1,
            {
                "options": "{{ ['test', 'yes', 'no'] }}",
                "select_option": [],
                "state": "{{ states('select.test_state') }}",
                "availability": "{{ is_state('binary_sensor.test_availability', 'on') }}",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_select")
async def test_availability(hass: HomeAssistant) -> None:
    """Test configuration with optimistic state."""

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "on")
    hass.states.async_set(TEST_STATE_ENTITY_ID, "test")
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "test"

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "off")
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_STATE_ENTITY_ID, "yes")
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "on")
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_SELECT)
    assert state.state == "yes"


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        select.DOMAIN,
        {"name": "My template", **TEST_OPTIONS},
    )

    assert state["state"] == "test"
