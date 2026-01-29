"""The tests for the Template select platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import select
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
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry, assert_setup_component
from tests.conftest import WebSocketGenerator

TEST_STATE_ENTITY_ID = "select.test_state"
TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.test_availability"

TEST_SELECT = TemplatePlatformSetup(
    select.DOMAIN,
    None,
    "template_select",
    make_test_trigger(TEST_STATE_ENTITY_ID, TEST_AVAILABILITY_ENTITY_ID),
)

TEST_OPTIONS_WITHOUT_STATE = {
    "options": "{{ ['test', 'yes', 'no'] }}",
    "select_option": [],
}
TEST_OPTIONS = {"state": "test", **TEST_OPTIONS_WITHOUT_STATE}
TEST_OPTION_ACTION = {
    "action": "test.automation",
    "data": {
        "action": "select_option",
        "caller": "{{ this.entity_id }}",
        "option": "{{ option }}",
    },
}


@pytest.fixture
async def setup_select(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of select integration."""
    await setup_entity(hass, TEST_SELECT, style, count, config)


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
            "select_option": [],
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_template")
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "config",
    [
        {
            "state": "{{ 'a' }}",
            "select_option": {"service": "script.select_option"},
            "options": "{{ ['a', 'b'] }}",
        },
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_select")
async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
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
    _verify(hass, "a", ["a", "b"], f"{TEST_SELECT.entity_id}_2")


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "config",
    [
        {
            "state": "{{ 'a' }}",
            "select_option": {"service": "script.select_option"},
        },
        {
            "state": "{{ 'a' }}",
            "options": "{{ ['a', 'b'] }}",
        },
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_select")
async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    assert hass.states.async_all("select") == []


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "options": "{{ state_attr('select.test_state', 'options') or [] }}",
                "select_option": [TEST_OPTION_ACTION],
                "state": "{{ states('select.test_state') }}",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_select")
async def test_template_select(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test templates with values from other entities."""

    attributes = {"options": ["a", "b"]}
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "a", attributes)
    _verify(hass, "a", ["a", "b"])

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "b", attributes)
    _verify(hass, "b", ["a", "b"])

    attributes = {"options": ["a", "b", "c"]}
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "b", attributes)
    _verify(hass, "b", ["a", "b", "c"])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SELECT_SERVICE_SELECT_OPTION,
        {CONF_ENTITY_ID: TEST_SELECT.entity_id, SELECT_ATTR_OPTION: "c"},
        blocking=True,
    )

    # Check this variable can be used in set_value script
    assert len(calls) == 1
    assert calls[-1].data["action"] == "select_option"
    assert calls[-1].data["caller"] == TEST_SELECT.entity_id
    assert calls[-1].data["option"] == "c"

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "c", attributes)
    _verify(hass, "c", ["a", "b", "c"])


def _verify(
    hass: HomeAssistant,
    expected_current_option: str,
    expected_options: list[str],
    entity_name: str = TEST_SELECT.entity_id,
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
    ("config", "attribute", "expected"),
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
    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.attributes.get(attribute) == initial_expected_state

    state = hass.states.async_set(TEST_STATE_ENTITY_ID, "yes")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SELECT.entity_id)

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
            "select_option": [],
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
    ("count", "config"),
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
@pytest.mark.usefixtures("setup_select")
async def test_empty_action_config(hass: HomeAssistant) -> None:
    """Test configuration with empty script."""
    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: TEST_SELECT.entity_id, "option": "a"},
        blocking=True,
    )

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == "a"


@pytest.mark.parametrize(
    ("count", "config"),
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

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == STATE_UNKNOWN

    # Ensure Trigger template entities update.
    hass.states.async_set(TEST_STATE_ENTITY_ID, "anything")
    await hass.async_block_till_done()

    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: TEST_SELECT.entity_id, "option": "test"},
        blocking=True,
    )

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == "test"

    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: TEST_SELECT.entity_id, "option": "yes"},
        blocking=True,
    )

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == "yes"


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ states('select.test_state') }}",
                "optimistic": False,
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
async def test_not_optimistic(hass: HomeAssistant) -> None:
    """Test optimistic yaml option set to false."""
    # Ensure Trigger template entities update the options list
    hass.states.async_set(TEST_STATE_ENTITY_ID, "anything")
    await hass.async_block_till_done()

    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: TEST_SELECT.entity_id, "option": "test"},
        blocking=True,
    )

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("count", "config"),
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

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == "test"

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "off")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_STATE_ENTITY_ID, "yes")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SELECT.entity_id)
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "on")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SELECT.entity_id)
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


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
) -> None:
    """Test unique_id option only creates one vacuum per id."""
    await setup_and_test_unique_id(
        hass, TEST_SELECT, style, TEST_OPTIONS_WITHOUT_STATE, "{{ 'test' }}"
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to vacuum unique_ids."""
    await setup_and_test_nested_unique_id(
        hass,
        TEST_SELECT,
        style,
        entity_registry,
        TEST_OPTIONS_WITHOUT_STATE,
        "{{ 'test' }}",
    )
