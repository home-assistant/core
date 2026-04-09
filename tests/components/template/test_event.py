"""The tests for the Template event platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import event, template
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

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

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_restore_cache_with_extra_data,
)
from tests.conftest import WebSocketGenerator

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_EVENT = TemplatePlatformSetup(
    event.DOMAIN,
    None,
    "template_event",
    make_test_trigger(TEST_STATE_ENTITY_ID),
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


async def test_legacy_platform_config(hass: HomeAssistant) -> None:
    """Test a legacy platform does not create event entities."""
    with assert_setup_component(1, event.DOMAIN):
        assert await async_setup_component(
            hass,
            event.DOMAIN,
            {"event": {"platform": "template", "events": {TEST_EVENT.object_id: {}}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.states.async_all("event") == []


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


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "event": {
                    "name": TEST_EVENT.object_id,
                    "event_type": "{{ trigger.event.data.action }}",
                    "event_types": TEST_EVENT_TYPES_TEMPLATE,
                    "picture": "{{ '/local/dogs.png' }}",
                    "icon": "{{ 'mdi:pirate' }}",
                    "attributes": {
                        "plus_one": "{{ trigger.event.data.beer + 1 }}",
                        "plus_two": "{{ trigger.event.data.beer + 2 }}",
                    },
                },
            },
        },
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    count: int,
    domain: str,
    config: dict,
) -> None:
    """Test restoring trigger event entities."""
    restored_attributes = {
        "entity_picture": "/local/cats.png",
        "event_type": "hold",
        "icon": "mdi:ship",
        "plus_one": 55,
    }
    fake_state = State(
        TEST_EVENT.entity_id,
        "2021-01-01T23:59:59.123+00:00",
        restored_attributes,
    )
    fake_extra_data = {
        "last_event_type": "hold",
        "last_event_attributes": restored_attributes,
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    test_state = "2021-01-01T23:59:59.123+00:00"
    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == test_state
    for attr, value in restored_attributes.items():
        assert state.attributes[attr] == value
    assert "plus_two" not in state.attributes

    hass.bus.async_fire("test_event", {"action": "double", "beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state != test_state
    assert state.attributes["icon"] == "mdi:pirate"
    assert state.attributes["entity_picture"] == "/local/dogs.png"
    assert state.attributes["event_type"] == "double"
    assert state.attributes["event_types"] == ["single", "double", "hold"]
    assert state.attributes["plus_one"] == 3
    assert state.attributes["plus_two"] == 4


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "event": {
                    "name": TEST_EVENT.object_id,
                    "event_type": "{{ states('sensor.test_state') }}",
                    "event_types": TEST_EVENT_TYPES_TEMPLATE,
                },
            },
        },
    ],
)
async def test_event_entity_restore_state(
    hass: HomeAssistant,
    count: int,
    domain: str,
    config: dict,
) -> None:
    """Test restoring trigger event entities."""
    fake_state = State(
        TEST_EVENT.entity_id,
        "2021-01-01T23:59:59.123+00:00",
        {},
    )
    fake_extra_data = {
        "last_event_type": "hold",
        "last_event_attributes": {},
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    test_state = "2021-01-01T23:59:59.123+00:00"
    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state == test_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "double")

    state = hass.states.get(TEST_EVENT.entity_id)
    assert state.state != test_state
    assert state.attributes["event_type"] == "double"


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
