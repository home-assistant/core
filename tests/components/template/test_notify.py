"""The tests for the Template notify platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import notify, template
from homeassistant.components.template.notify import CONF_SEND_MESSAGE
from homeassistant.const import ATTR_ENTITY_PICTURE, ATTR_ICON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_restore_cache_with_extra_data,
)

TEST_OBJECT_ID = "template_notify"
TEST_ENTITY_ID = f"notify.{TEST_OBJECT_ID}"
TEST_SENSOR = "sensor.notify"
TEST_STATE_TRIGGER = {
    "trigger": {"trigger": "state", "entity_id": TEST_SENSOR},
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [
        {"event": "action_event", "event_data": {"what": "{{ triggering_entity }}"}}
    ],
}

TEST_SEND_MESSAGE_CONFIG = {
    CONF_SEND_MESSAGE: {
        "action": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "message": "{{ message }}",
            "title": "{{ title }}",
        },
    }
}
TEST_SEND_MESSAGE_CONFIG_NO_TITLE = {
    CONF_SEND_MESSAGE: {
        "action": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "message": "{{ message }}",
        },
    }
}
TEST_UNIQUE_ID_CONFIG = {
    **TEST_SEND_MESSAGE_CONFIG,
    "unique_id": "not-so-unique-anymore",
}
TEST_FROZEN_INPUT = "2025-06-19 00:00:00+00:00"
TEST_FROZEN_STATE = "2025-06-19T00:00:00.000+00:00"


async def async_setup_modern_format(
    hass: HomeAssistant,
    count: int,
    notify_config: dict[str, Any],
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of notify integration via new format."""
    extra = extra_config if extra_config else {}
    config = {**notify_config, **extra}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {"template": {"notify": config}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant,
    count: int,
    notify_config: dict[str, Any],
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of notify integration via trigger format."""
    extra = extra_config if extra_config else {}
    config = {
        "template": {
            **TEST_STATE_TRIGGER,
            "notify": {**notify_config, **extra},
        }
    }

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_notify_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    notify_config: dict[str, Any],
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of notify integration."""
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, notify_config, extra_config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, notify_config, extra_config)


@pytest.fixture
async def setup_base_notify(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    notify_config: dict[str, Any],
) -> None:
    """Do setup of notify integration."""
    await async_setup_notify_config(
        hass,
        count,
        style,
        notify_config,
        None,
    )


@pytest.fixture
async def setup_notify(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of notify integration."""
    await async_setup_notify_config(
        hass,
        count,
        style,
        {"name": TEST_OBJECT_ID, **TEST_SEND_MESSAGE_CONFIG},
        extra_config,
    )


@pytest.fixture
async def setup_single_attribute_state_notify(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of notify integration testing a single attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    config = {"name": TEST_OBJECT_ID, **TEST_SEND_MESSAGE_CONFIG}
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, config, extra)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, config, extra)


async def test_legacy_platform_config(hass: HomeAssistant) -> None:
    """Test a legacy platform does not create notify entities."""
    with assert_setup_component(1, notify.DOMAIN):
        assert await async_setup_component(
            hass,
            notify.DOMAIN,
            {"notify": {"platform": "template", "notifys": {TEST_OBJECT_ID: {}}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.states.async_all("notify") == []


@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    hass.states.async_set(
        TEST_SENSOR,
        "single",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": TEST_OBJECT_ID,
            "template_type": notify.DOMAIN,
            **TEST_SEND_MESSAGE_CONFIG,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
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
            **TEST_SEND_MESSAGE_CONFIG,
            "template_type": "notify",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("notify.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [(ConfigurationStyle.MODERN, ""), (ConfigurationStyle.TRIGGER, None)],
)
@pytest.mark.parametrize(
    ("attribute", "attribute_template", "key", "expected"),
    [
        (
            "picture",
            "{% if is_state('sensor.notify', 'double') %}something{% endif %}",
            ATTR_ENTITY_PICTURE,
            "something",
        ),
        (
            "icon",
            "{% if is_state('sensor.notify', 'double') %}mdi:something{% endif %}",
            ATTR_ICON,
            "mdi:something",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_notify")
async def test_entity_picture_and_icon_templates(
    hass: HomeAssistant, key: str, initial_state: str, expected: str
) -> None:
    """Test picture and icon template."""
    state = hass.states.async_set(TEST_SENSOR, "single")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(key) == initial_state

    state = hass.states.async_set(TEST_SENSOR, "double")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state.attributes[key] == expected


@pytest.mark.parametrize(
    (
        "count",
        "attribute",
        "attribute_template",
    ),
    [
        (
            1,
            "availability",
            "{{ states('sensor.notify') in ['yes', 'no'] }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_notify")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    hass.states.async_set(TEST_SENSOR, "yes")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(TEST_SENSOR, "maybe")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "notify": {
                    "name": TEST_OBJECT_ID,
                    "picture": "{{ '/local/dogs.png' }}",
                    "icon": "{{ 'mdi:pirate' }}",
                    **TEST_SEND_MESSAGE_CONFIG,
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
    """Test restoring trigger notify entities."""
    restored_attributes = {
        "entity_picture": "/local/cats.png",
        "icon": "mdi:ship",
    }
    fake_state = State(
        TEST_ENTITY_ID,
        "2021-01-01T23:59:59.123+00:00",
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

    test_state = "2021-01-01T23:59:59.123+00:00"
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == test_state
    for attr, value in restored_attributes.items():
        assert state.attributes[attr] == value

    hass.bus.async_fire("test_event", {"action": "double", "beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state != test_state
    assert state.attributes["icon"] == "mdi:pirate"
    assert state.attributes["entity_picture"] == "/local/dogs.png"


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "notify": {"name": TEST_OBJECT_ID, **TEST_SEND_MESSAGE_CONFIG},
            },
        },
    ],
)
@pytest.mark.freeze_time(TEST_FROZEN_INPUT)
async def test_notify_entity_restore_state(
    hass: HomeAssistant,
    count: int,
    domain: str,
    config: dict,
    calls: list[ServiceCall],
) -> None:
    """Test restoring trigger notify entities."""
    fake_state = State(
        TEST_ENTITY_ID,
        "2021-01-01T23:59:59.123+00:00",
        {},
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

    test_state = "2021-01-01T23:59:59.123+00:00"
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == test_state

    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {notify.ATTR_MESSAGE: "This is a test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == TEST_FROZEN_STATE


@pytest.mark.parametrize(
    (
        "count",
        "attribute",
        "attribute_template",
    ),
    [
        (
            1,
            "availability",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_notify")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text,
) -> None:
    """Test that an invalid availability keeps the device available."""
    hass.states.async_set(TEST_SENSOR, "anything")
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE

    error = "UndefinedError: 'x' is undefined"
    assert error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("notifys", "style"),
    [
        (
            [
                {
                    "name": "test_template_notify_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_notify_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
        (
            [
                {
                    "name": "test_template_notify_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_notify_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
async def test_unique_id(
    hass: HomeAssistant, count: int, notifys: list[dict], style: ConfigurationStyle
) -> None:
    """Test unique_id option only creates one notify per id."""
    config = {"notify": notifys}
    if style == ConfigurationStyle.TRIGGER:
        config = {**config, **TEST_STATE_TRIGGER}
    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {"template": config},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("notify")) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option creates one notify per nested id."""

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "notify": [
                        {
                            "name": "test_a",
                            **TEST_SEND_MESSAGE_CONFIG,
                            "unique_id": "a",
                        },
                        {
                            "name": "test_b",
                            **TEST_SEND_MESSAGE_CONFIG,
                            "unique_id": "b",
                        },
                    ],
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("notify")) == 2

    entry = entity_registry.async_get("notify.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("notify.test_b")
    assert entry
    assert entry.unique_id == "x-b"
