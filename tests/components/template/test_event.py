"""The tests for the Template event platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import event, template
from homeassistant.components.template.const import CONF_ATTRIBUTES, CONF_PICTURE
from homeassistant.components.template.coordinator import TriggerUpdateCoordinator
from homeassistant.components.template.event import (
    CONF_EVENT_TYPE,
    CONF_EVENT_TYPES,
    TriggerEventEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    CONF_ICON,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.template import Template

from .conftest import (
    RESTORE_STATE_SAVED_ATTRIBUTES,
    RESTORE_STATE_UPDATED_ATTRIBUTES,
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_state_and_attributes,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
    setup_mock_template_entity_restore_state,
    setup_restore_template_entity,
)

from tests.common import MockConfigEntry, MockEntityPlatform, mock_restore_cache
from tests.conftest import WebSocketGenerator

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_EVENT = TemplatePlatformSetup(
    event.DOMAIN,
    "template_event",
    make_test_trigger(TEST_STATE_ENTITY_ID, TEST_ATTRIBUTE_ENTITY_ID),
)

TEST_EVENT_TYPES_TEMPLATE = "{{ ['single', 'double', 'hold'] }}"
TEST_EVENT_TYPE_TEMPLATE = "{{ 'single' }}"

TEST_EVENT_CONFIG = {
    "event_types": TEST_EVENT_TYPES_TEMPLATE,
    "event_type": TEST_EVENT_TYPE_TEMPLATE,
}
TEST_FROZEN_INPUT = "2024-07-09 00:00:00+00:00"
TEST_FROZEN_STATE = "2024-07-09T00:00:00.000+00:00"


@pytest.fixture
async def setup_base_event(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of event integration."""
    await setup_entity(hass, TEST_EVENT, style, count, config)


@pytest.fixture
async def setup_event(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    event_type_template: str,
    event_types_template: str,
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of event integration."""
    await setup_entity(
        hass,
        TEST_EVENT,
        style,
        count,
        {
            "event_type": event_type_template,
            "event_types": event_types_template,
        },
        extra_config=extra_config,
    )


@pytest.fixture
async def setup_single_attribute_state_event(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    event_type_template: str,
    event_types_template: str,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of event integration testing a single attribute."""
    await setup_entity(
        hass,
        TEST_EVENT,
        style,
        count,
        {
            "event_type": event_type_template,
            "event_types": event_types_template,
        },
        extra_config={attribute: attribute_template}
        if attribute and attribute_template
        else {},
    )


@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "single",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": TEST_EVENT.object_id,
            **TEST_EVENT_CONFIG,
            "template_type": event.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state is not None
    assert state == snapshot


@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
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
            "event_type": TEST_EVENT_TYPE_TEMPLATE,
            "event_types": TEST_EVENT_TYPES_TEMPLATE,
            "template_type": "event",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("event.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(
    ("count", "event_types_template", "extra_config"),
    [(1, TEST_EVENT_TYPES_TEMPLATE, None)],
)
@pytest.mark.parametrize(
    ("style", "expected_state"),
    [
        (ConfigurationStyle.MODERN, STATE_UNKNOWN),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize("event_type_template", ["{{states.test['big.fat...']}}"])
@pytest.mark.usefixtures("setup_event")
async def test_event_type_syntax_error(
    hass: HomeAssistant,
    expected_state: str,
) -> None:
    """Test template event_type with render error."""
    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("count", "event_type_template", "event_types_template", "extra_config"),
    [(1, "{{ states('sensor.test_state') }}", TEST_EVENT_TYPES_TEMPLATE, None)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ("single", "single"),
        ("double", "double"),
        ("hold", "hold"),
    ],
)
@pytest.mark.usefixtures("setup_event")
async def test_event_type_template(
    hass: HomeAssistant,
    event: str,
    expected: str,
) -> None:
    """Test template event_type."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, event)

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.attributes["event_type"] == expected


@pytest.mark.parametrize(
    ("count", "event_type_template", "event_types_template", "extra_config"),
    [(1, "{{ states('sensor.test_state') }}", TEST_EVENT_TYPES_TEMPLATE, None)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_event")
@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_event_type_template_updates(
    hass: HomeAssistant,
) -> None:
    """Test template event_type updates."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "single")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == TEST_FROZEN_STATE
    assert state.attributes["event_type"] == "single"

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "double")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == TEST_FROZEN_STATE
    assert state.attributes["event_type"] == "double"

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "hold")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == TEST_FROZEN_STATE
    assert state.attributes["event_type"] == "hold"


@pytest.mark.parametrize(
    ("count", "event_types_template", "extra_config"),
    [(1, TEST_EVENT_TYPES_TEMPLATE, None)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "event_type_template",
    [
        "{{ None }}",
        "{{ 7 }}",
        "{{ 'unknown' }}",
        "{{ 'tripple_double' }}",
    ],
)
@pytest.mark.usefixtures("setup_event")
async def test_event_type_invalid(
    hass: HomeAssistant,
) -> None:
    """Test template event_type."""
    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["event_type"] is None


@pytest.mark.parametrize(
    ("count", "event_type_template", "event_types_template"),
    [(1, "{{ states('sensor.test_state') }}", TEST_EVENT_TYPES_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute", "attribute_template", "key", "expected"),
    [
        (
            "picture",
            "{% if is_state('sensor.test_state', 'double') %}something{% endif %}",
            ATTR_ENTITY_PICTURE,
            "something",
        ),
        (
            "icon",
            "{% if is_state('sensor.test_state', 'double') %}mdi:something{% endif %}",
            ATTR_ICON,
            "mdi:something",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_event")
async def test_entity_picture_and_icon_templates(
    hass: HomeAssistant, key: str, expected: str
) -> None:
    """Test picture and icon template."""
    state = await async_trigger(hass, TEST_STATE_ENTITY_ID, "single")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.attributes.get(key) in ("", None)

    state = await async_trigger(hass, TEST_STATE_ENTITY_ID, "double")

    state = hass.states.get(TEST_EVENT.entity_id)

    assert state.attributes[key] == expected


@pytest.mark.parametrize(
    ("count", "event_type_template", "extra_config"),
    [(1, "{{ None }}", None)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("event_types_template", "expected"),
    [
        (
            "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}",
            ["Strobe color", "Police", "Christmas", "RGB", "Random Loop"],
        ),
        (
            "{{ ['Police', 'RGB', 'Random Loop'] }}",
            ["Police", "RGB", "Random Loop"],
        ),
        ("{{ [] }}", []),
        ("{{ '[]' }}", []),
        ("{{ 124 }}", []),
        ("{{ '124' }}", []),
        ("{{ none }}", []),
        ("", []),
    ],
)
@pytest.mark.usefixtures("setup_event")
async def test_event_types_template(hass: HomeAssistant, expected: str) -> None:
    """Test template event_types."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.attributes["event_types"] == expected


@pytest.mark.parametrize(
    ("count", "event_type_template", "event_types_template", "extra_config"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ state_attr('sensor.test_state', 'options') or ['unknown'] }}",
            None,
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_event")
@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_event_types_template_updates(hass: HomeAssistant) -> None:
    """Test template event_type update with entity."""
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "single", {"options": ["single", "double", "hold"]}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == TEST_FROZEN_STATE
    assert state.attributes["event_type"] == "single"
    assert state.attributes["event_types"] == ["single", "double", "hold"]

    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "double", {"options": ["double", "hold"]}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == TEST_FROZEN_STATE
    assert state.attributes["event_type"] == "double"
    assert state.attributes["event_types"] == ["double", "hold"]


@pytest.mark.parametrize(
    (
        "count",
        "event_type_template",
        "event_types_template",
        "attribute",
        "attribute_template",
    ),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            TEST_EVENT_TYPES_TEMPLATE,
            "availability",
            "{{ states('sensor.test_state') in ['single', 'double', 'hold'] }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_event")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "single")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["event_type"] == "single"

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "triple")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert "event_type" not in state.attributes


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "event_type": "{{ states('sensor.test_state') }}",
            "event_types": TEST_EVENT_TYPES_TEMPLATE,
            "attributes": {
                "plus_one": "{{ states('sensor.test_attribute') | int(0) + 1 }}",
                "plus_two": "{{ states('sensor.test_attribute') | int(0) + 2 }}",
            },
        },
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict,
) -> None:
    """Test restoring template event entities."""

    # Ensure the initial state is None so that restore data is honored
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    restored_attributes = {
        "plus_one": 55,
    }
    setup_mock_template_entity_restore_state(
        hass,
        TEST_EVENT,
        "2021-01-01T23:59:59.123+00:00",
        saved_extra_data={
            "last_event_type": "hold",
            "last_event_attributes": restored_attributes,
        },
        saved_attributes=restored_attributes,
    )
    await setup_restore_template_entity(
        hass, TEST_EVENT, style, config, "is_state('sensor.test_attribute', '2')"
    )

    test_state = "2021-01-01T23:59:59.123+00:00"
    state = assert_state_and_attributes(
        hass,
        TEST_EVENT,
        test_state,
        {**restored_attributes, **RESTORE_STATE_SAVED_ATTRIBUTES},
    )
    assert "plus_two" not in state.attributes

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "double")
    await async_trigger(hass, TEST_ATTRIBUTE_ENTITY_ID, 2)

    state = assert_state_and_attributes(
        hass,
        TEST_EVENT,
        expected_attributes={
            "plus_one": 3,
            "plus_two": 4,
            "event_type": "double",
            "event_types": ["single", "double", "hold"],
            **RESTORE_STATE_UPDATED_ATTRIBUTES,
        },
    )
    assert state.state != test_state


def _make_trigger_event_entity(hass: HomeAssistant) -> TriggerEventEntity:
    """Create a trigger event entity that renders fresh, static attributes."""
    config = {
        CONF_NAME: Template("fresh_name", hass),
        CONF_ICON: Template("mdi:fresh", hass),
        CONF_PICTURE: Template("/local/fresh.png", hass),
        CONF_EVENT_TYPE: Template("fresh", hass),
        CONF_EVENT_TYPES: Template("{{ ['fresh'] }}", hass),
        CONF_ATTRIBUTES: {"attr": Template("fresh_attr", hass)},
    }
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TriggerEventEntity(hass, coordinator, config)
    entity.entity_id = "event.test"
    entity.platform = MockEntityPlatform(hass)
    return entity


def _mock_stale_restore_cache(hass: HomeAssistant) -> None:
    """Prime the restore cache with stale attributes for the test entity."""
    mock_restore_cache(
        hass,
        (
            State(
                "event.test",
                "2021-01-01T00:00:00+00:00",
                {
                    ATTR_FRIENDLY_NAME: "stale_name",
                    ATTR_ICON: "mdi:stale",
                    ATTR_ENTITY_PICTURE: "/local/stale.png",
                    "attr": "stale_attr",
                },
            ),
        ),
    )


async def test_trigger_restore_does_not_clobber_rendered_attributes(
    hass: HomeAssistant,
) -> None:
    """A trigger that already fired must win over restored state.

    Regression test for the race where the trigger fires (populating the
    coordinator) before the entity is added to hass. ``_process_data`` renders
    fresh attributes which restore would otherwise overwrite with stale values.
    """
    entity = _make_trigger_event_entity(hass)
    # Simulate the trigger having already fired before the entity is added.
    entity.coordinator._execute_update({})
    assert entity.coordinator.data is not None

    _mock_stale_restore_cache(hass)

    await entity.async_added_to_hass()
    await hass.async_block_till_done()

    # The freshly rendered values must win over the stale restored ones.
    assert entity.name == "fresh_name"
    assert entity.icon == "mdi:fresh"
    assert entity.entity_picture == "/local/fresh.png"
    assert entity.extra_state_attributes == {"attr": "fresh_attr"}


async def test_trigger_restores_when_not_yet_triggered(
    hass: HomeAssistant,
) -> None:
    """When the trigger has not fired, restored attributes are applied."""
    entity = _make_trigger_event_entity(hass)
    assert entity.coordinator.data is None

    _mock_stale_restore_cache(hass)

    await entity.async_added_to_hass()
    await hass.async_block_till_done()

    # No fresh data yet, so the restored values are surfaced.
    assert entity.name == "stale_name"
    assert entity.icon == "mdi:stale"
    assert entity.entity_picture == "/local/stale.png"
    assert entity.extra_state_attributes == {"attr": "stale_attr"}


@pytest.mark.parametrize(
    (
        "count",
        "event_type_template",
        "event_types_template",
        "attribute",
        "attribute_template",
    ),
    [
        (
            1,
            TEST_EVENT_TYPE_TEMPLATE,
            TEST_EVENT_TYPES_TEMPLATE,
            "availability",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_event")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text,
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    assert hass.states.get(TEST_EVENT.entity_id).state != STATE_UNAVAILABLE

    error = "UndefinedError: 'x' is undefined"
    assert error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test unique_id option only creates one event per id."""
    await setup_and_test_unique_id(hass, TEST_EVENT, style, TEST_EVENT_CONFIG)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to event unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_EVENT, style, entity_registry, TEST_EVENT_CONFIG
    )


@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        event.DOMAIN,
        {"name": "My template", **TEST_EVENT_CONFIG},
    )

    assert state["state"] == TEST_FROZEN_STATE
    assert state["attributes"]["event_type"] == "single"
    assert state["attributes"]["event_types"] == ["single", "double", "hold"]
