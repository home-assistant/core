"""The tests for the Template Binary sensor platform."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import binary_sensor, template
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    async_get_flow_preview_state,
    async_setup_legacy_platforms,
    async_setup_modern_state_format,
    async_setup_modern_trigger_format,
    make_test_trigger,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)
from tests.typing import WebSocketGenerator

_BEER_TRIGGER_VALUE_TEMPLATE = (
    "{% if trigger.event.data.beer < 0 %}"
    "{{ 1 / 0 == 10 }}"
    "{% elif trigger.event.data.beer == 0 %}"
    "{{ None }}"
    "{% else %}"
    "{{ trigger.event.data.beer == 2 }}"
    "{% endif %}"
)


TEST_OBJECT_ID = "test_binary_sensor"
TEST_ENTITY_ID = f"binary_sensor.{TEST_OBJECT_ID}"
TEST_STATE_ENTITY_ID = "binary_sensor.test_state"
TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.test_availability"
TEST_STATE_TRIGGER = make_test_trigger(
    TEST_STATE_ENTITY_ID, TEST_AVAILABILITY_ENTITY_ID, TEST_ATTRIBUTE_ENTITY_ID
)
UNIQUE_ID_CONFIG = {
    "unique_id": "not-so-unique-anymore",
}


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, config: ConfigType
) -> None:
    """Do setup of binary sensor integration via legacy format."""
    await async_setup_legacy_platforms(
        hass, binary_sensor.DOMAIN, "sensors", count, config
    )


async def async_setup_modern_format(
    hass: HomeAssistant,
    count: int,
    config: ConfigType,
    extra_config: ConfigType | None = None,
) -> None:
    """Do setup of binary sensor integration via modern format."""
    await async_setup_modern_state_format(
        hass, binary_sensor.DOMAIN, count, config, extra_config
    )


async def async_setup_trigger_format(
    hass: HomeAssistant,
    count: int,
    config: ConfigType,
    extra_config: ConfigType | None = None,
) -> None:
    """Do setup of binary sensor integration via trigger format."""
    await async_setup_modern_trigger_format(
        hass, binary_sensor.DOMAIN, TEST_STATE_TRIGGER, count, config, extra_config
    )


@pytest.fixture
async def setup_base_binary_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType | list[dict],
    extra_template_options: ConfigType,
) -> None:
    """Do setup of binary sensor integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, config, extra_template_options)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, config, extra_template_options)


async def async_setup_binary_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: ConfigType,
) -> None:
    """Do setup of binary sensor integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {TEST_OBJECT_ID: {"value_template": state_template, **extra_config}},
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {"name": TEST_OBJECT_ID, "state": state_template, **extra_config},
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {"name": TEST_OBJECT_ID, "state": state_template, **extra_config},
        )


@pytest.fixture
async def setup_binary_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: dict[str, Any],
) -> None:
    """Do setup of binary sensor integration."""
    await async_setup_binary_sensor(hass, count, style, state_template, extra_config)


@pytest.fixture
async def setup_single_attribute_binary_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_value: str | dict,
    state_template: str,
    extra_config: dict,
) -> None:
    """Do setup of binary sensor integration testing a single attribute."""
    extra = {attribute: attribute_value} if attribute and attribute_value else {}
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    "value_template": state_template,
                    **extra,
                    **extra_config,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "state": state_template,
                **extra,
                **extra_config,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "state": state_template,
                **extra,
                **extra_config,
            },
        )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"), [(1, "{{ True }}", {})]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_setup_minimal(hass: HomeAssistant) -> None:
    """Test the setup."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.name == TEST_OBJECT_ID
    assert state.state == STATE_ON
    assert state.attributes == {"friendly_name": TEST_OBJECT_ID}


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [
        (
            1,
            "{{ True }}",
            {
                "device_class": "motion",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_setup(hass: HomeAssistant) -> None:
    """Test the setup."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.name == TEST_OBJECT_ID
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "motion"


@pytest.mark.parametrize(
    "config_entry_extra_options",
    [
        {},
        {"device_class": "battery"},
    ],
)
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry_extra_options: dict[str, str],
) -> None:
    """Test the config flow."""
    state_template = (
        "{{ states('binary_sensor.one') == 'on' or "
        "   states('binary_sensor.two') == 'on' }}"
    )
    input_entities = ["one", "two"]
    input_states = {"one": "on", "two": "off"}
    template_type = binary_sensor.DOMAIN

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}",
            input_states[input_entity],
            {},
        )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": state_template,
            "template_type": template_type,
        }
        | config_entry_extra_options,
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{template_type}.my_template")
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    ("config", "domain"),
    [
        # No legacy binary sensors
        (
            {"binary_sensor": {"platform": "template"}},
            binary_sensor.DOMAIN,
        ),
        # Legacy binary sensor missing mandatory config
        (
            {"binary_sensor": {"platform": "template", "sensors": {"foo bar": {}}}},
            binary_sensor.DOMAIN,
        ),
        # Binary sensor missing mandatory config
        (
            {"template": {"binary_sensor": {}}},
            template.DOMAIN,
        ),
        # Legacy binary sensor with invalid device class
        (
            {
                "binary_sensor": {
                    "platform": "template",
                    "sensors": {
                        "test": {
                            "value_template": "{{ foo }}",
                            "device_class": "foobarnotreal",
                        }
                    },
                }
            },
            binary_sensor.DOMAIN,
        ),
        # Binary sensor with invalid device class
        (
            {
                "template": {
                    "binary_sensor": {
                        "state": "{{ foo }}",
                        "device_class": "foobarnotreal",
                    }
                }
            },
            template.DOMAIN,
        ),
        # Legacy binary sensor missing mandatory config
        (
            {
                "binary_sensor": {
                    "platform": "template",
                    "sensors": {"test": {"device_class": "motion"}},
                }
            },
            binary_sensor.DOMAIN,
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_setup_invalid_sensors(hass: HomeAssistant, count: int) -> None:
    """Test setup with no sensors."""
    assert len(hass.states.async_entity_ids("binary_sensor")) == count


@pytest.mark.parametrize(
    ("state_template", "expected_result"),
    [
        ("{{ None }}", STATE_UNKNOWN),
        ("{{ True }}", STATE_ON),
        ("{{ False }}", STATE_OFF),
        ("{{ 1 }}", STATE_ON),
        (
            "{% if states('binary_sensor.three') in ('unknown','unavailable') %}"
            "{{ None }}"
            "{% else %}"
            "{{ states('binary_sensor.three') == 'off' }}"
            "{% endif %}",
            STATE_UNKNOWN,
        ),
        ("{{ 1 / 0 == 10 }}", STATE_UNAVAILABLE),
    ],
)
async def test_state(
    hass: HomeAssistant,
    state_template: str,
    expected_result: str,
) -> None:
    """Test the config flow."""
    hass.states.async_set("binary_sensor.one", "on")
    hass.states.async_set("binary_sensor.two", "off")
    hass.states.async_set("binary_sensor.three", "unknown")

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": state_template,
            "template_type": binary_sensor.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.my_template")
    assert state is not None
    assert state.state == expected_result


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{% if is_state('binary_sensor.test_state', 'on') %}mdi:check{% endif %}",
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, "icon_template", ""),
        (ConfigurationStyle.MODERN, "icon", ""),
        (ConfigurationStyle.TRIGGER, "icon", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_icon_template(hass: HomeAssistant, initial_state: str | None) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") == initial_state

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{% if is_state('binary_sensor.test_state', 'on') %}/local/sensor.png{% endif %}",
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template", ""),
        (ConfigurationStyle.MODERN, "picture", ""),
        (ConfigurationStyle.TRIGGER, "picture", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_entity_picture_template(
    hass: HomeAssistant, initial_state: str | None
) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") == initial_state

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["entity_picture"] == "/local/sensor.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [
        (
            1,
            "{{ True }}",
            {"test_attribute": "It {{ states.sensor.test_attribute.state }}."},
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_value"),
    [
        (ConfigurationStyle.LEGACY, "attribute_templates", "It ."),
        (ConfigurationStyle.MODERN, "attributes", "It ."),
        (ConfigurationStyle.TRIGGER, "attributes", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_attribute_templates(
    hass: HomeAssistant, initial_value: str | None
) -> None:
    """Test attribute_templates template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("test_attribute") == initial_value

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "Works2")
    await hass.async_block_till_done()
    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "Works")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["test_attribute"] == "It Works."


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [
        (
            1,
            "{{ states.binary_sensor.test_sensor }}",
            {"test_attribute": "{{ states.binary_sensor.unknown.attributes.picture }}"},
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "attribute_templates"),
        (ConfigurationStyle.MODERN, "attributes"),
        (ConfigurationStyle.TRIGGER, "attributes"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_invalid_attribute_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog_setup_text: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that errors are logged if rendering template fails."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2
    text = (
        "Template variable error: 'None' has no attribute 'attributes' when rendering"
    )
    assert text in caplog_setup_text or text in caplog.text


@pytest.fixture
def setup_mock() -> Generator[Mock]:
    """Do setup of sensor mock."""
    with patch(
        "homeassistant.components.template.binary_sensor."
        "StateBinarySensorEntity._update_state"
    ) as _update_state:
        yield _update_state


@pytest.mark.parametrize(("count", "domain"), [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "match_all_template_sensor": {
                        "value_template": (
                            "{% for state in states %}"
                            "{% if state.entity_id == 'sensor.humidity' %}"
                            "{{ state.entity_id }}={{ state.state }}"
                            "{% endif %}"
                            "{% endfor %}"
                        ),
                    },
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_match_all(hass: HomeAssistant, setup_mock: Mock) -> None:
    """Test template that is rerendered on any state lifecycle."""
    init_calls = len(setup_mock.mock_calls)

    hass.states.async_set("sensor.any_state", "update")
    await hass.async_block_till_done()
    assert len(setup_mock.mock_calls) == init_calls


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [
        (
            1,
            "{{ is_state('binary_sensor.test_state', 'on') }}",
            {"device_class": "motion"},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, STATE_OFF),
        (ConfigurationStyle.MODERN, STATE_OFF),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_binary_sensor_state(hass: HomeAssistant, initial_state: str) -> None:
    """Test the event."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == initial_state

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ is_state('binary_sensor.test_state', 'on') }}",
            {"device_class": "motion"},
            "delay_on",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, STATE_OFF),
        (ConfigurationStyle.MODERN, STATE_OFF),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "attribute_value",
    [
        5,
        "{{ dict(seconds=10 / 2) }}",
        '{{ dict(seconds=states("sensor.test_attribute") | int(0)) }}',
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_delay_on(
    hass: HomeAssistant, initial_state: str, freezer: FrozenDateTimeFactory
) -> None:
    """Test binary sensor template delay on."""
    # Ensure the initial state is not on
    assert hass.states.get(TEST_ENTITY_ID).state == initial_state

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, 5)
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == initial_state

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_OFF

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_OFF

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_OFF

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ is_state('binary_sensor.test_state', 'on') }}",
            {"device_class": "motion"},
            "delay_off",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize(
    "attribute_value",
    [
        5,
        "{{ dict(seconds=10 / 2) }}",
        '{{ dict(seconds=states("sensor.test_attribute") | int(0)) }}',
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_delay_off(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test binary sensor template delay off."""
    assert hass.states.get(TEST_ENTITY_ID).state != STATE_ON

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, 5)
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_ON

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [
        (
            1,
            "{{ True }}",
            {
                "device_class": "motion",
                "delay_off": 5,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_available_without_availability_template(hass: HomeAssistant) -> None:
    """Ensure availability is true without an availability_template."""
    state = hass.states.get(TEST_ENTITY_ID)

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [
        (
            1,
            "{{ True }}",
            "{{ is_state('binary_sensor.test_availability','on') }}",
            {
                "device_class": "motion",
                "delay_off": 5,
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_availability_template(hass: HomeAssistant) -> None:
    """Test availability template."""
    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [(1, "{{ True }}", "{{ x - 12 }}", {})],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""

    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE
    text = "UndefinedError: 'x' is undefined"
    assert text in caplog_setup_text or text in caplog.text


async def test_no_update_template_match_all(hass: HomeAssistant) -> None:
    """Test that we do not update sensors that match on all."""

    hass.set_state(CoreState.not_running)

    await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "all_state": {"value_template": '{{ "true" }}'},
                    "all_icon": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "icon_template": "{{ 1 + 1 }}",
                    },
                    "all_entity_picture": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "entity_picture_template": "{{ 1 + 1 }}",
                    },
                    "all_attribute": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "attribute_templates": {"test_attribute": "{{ 1 + 1 }}"},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.test_sensor", STATE_ON)
    assert len(hass.states.async_all()) == 5

    assert hass.states.get("binary_sensor.all_state").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.all_icon").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.all_entity_picture").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.all_attribute").state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == STATE_ON
    assert hass.states.get("binary_sensor.all_icon").state == STATE_ON
    assert hass.states.get("binary_sensor.all_entity_picture").state == STATE_ON
    assert hass.states.get("binary_sensor.all_attribute").state == STATE_ON

    hass.states.async_set("binary_sensor.test_sensor", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == STATE_ON
    # Will now process because we have one valid template
    assert hass.states.get("binary_sensor.all_icon").state == STATE_OFF
    assert hass.states.get("binary_sensor.all_entity_picture").state == STATE_OFF
    assert hass.states.get("binary_sensor.all_attribute").state == STATE_OFF

    await async_update_entity(hass, "binary_sensor.all_state")
    await async_update_entity(hass, "binary_sensor.all_icon")
    await async_update_entity(hass, "binary_sensor.all_entity_picture")
    await async_update_entity(hass, "binary_sensor.all_attribute")

    assert hass.states.get("binary_sensor.all_state").state == STATE_ON
    assert hass.states.get("binary_sensor.all_icon").state == STATE_OFF
    assert hass.states.get("binary_sensor.all_entity_picture").state == STATE_OFF
    assert hass.states.get("binary_sensor.all_attribute").state == STATE_OFF


@pytest.mark.parametrize(("count", "extra_template_options"), [(1, {})])
@pytest.mark.parametrize(
    ("config", "style"),
    [
        (
            {
                "test_template_01": {
                    "value_template": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
                "test_template_02": {
                    "value_template": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_01",
                    "state": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_02",
                    "state": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
        (
            [
                {
                    "name": "test_template_01",
                    "state": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_02",
                    "state": "{{ True }}",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_binary_sensor")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one fan per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(
    ("count", "config", "extra_template_options"),
    [
        (
            1,
            [
                {
                    "name": "test_a",
                    "state": "{{ True }}",
                    "unique_id": "a",
                },
                {
                    "name": "test_b",
                    "state": "{{ True }}",
                    "unique_id": "b",
                },
            ],
            {"unique_id": "x"},
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_base_binary_sensor")
async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    assert len(hass.states.async_all("binary_sensor")) == 2

    entry = entity_registry.async_get("binary_sensor.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("binary_sensor.test_b")
    assert entry
    assert entry.unique_id == "x-b"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_value", "extra_config"),
    [(1, "{{ 1 == 1 }}", "{{ states.sensor.test_attribute.state }}", {})],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, "icon_template", ""),
        (ConfigurationStyle.MODERN, "icon", ""),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_template_icon_validation_error(
    hass: HomeAssistant, initial_state: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test binary sensor template delay on."""
    caplog.set_level(logging.ERROR)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") == initial_state

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "mdi:check")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:check"

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "invalid_icon")
    await hass.async_block_till_done()

    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith(
        "Error validating template result 'invalid_icon' from template"
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") is None


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.binary_sensor.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
@pytest.mark.parametrize(
    ("extra_config", "source_state", "restored_state", "initial_state"),
    [
        ({}, STATE_OFF, STATE_ON, STATE_OFF),
        ({}, STATE_OFF, STATE_OFF, STATE_OFF),
        ({}, STATE_OFF, STATE_UNAVAILABLE, STATE_OFF),
        ({}, STATE_OFF, STATE_UNKNOWN, STATE_OFF),
        ({"delay_off": 5}, STATE_OFF, STATE_ON, STATE_ON),
        ({"delay_off": 5}, STATE_OFF, STATE_OFF, STATE_OFF),
        ({"delay_off": 5}, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN),
        ({"delay_off": 5}, STATE_OFF, STATE_UNKNOWN, STATE_UNKNOWN),
        ({"delay_on": 5}, STATE_OFF, STATE_ON, STATE_OFF),
        ({"delay_on": 5}, STATE_OFF, STATE_OFF, STATE_OFF),
        ({"delay_on": 5}, STATE_OFF, STATE_UNAVAILABLE, STATE_OFF),
        ({"delay_on": 5}, STATE_OFF, STATE_UNKNOWN, STATE_OFF),
        ({}, STATE_ON, STATE_ON, STATE_ON),
        ({}, STATE_ON, STATE_OFF, STATE_ON),
        ({}, STATE_ON, STATE_UNAVAILABLE, STATE_ON),
        ({}, STATE_ON, STATE_UNKNOWN, STATE_ON),
        ({"delay_off": 5}, STATE_ON, STATE_ON, STATE_ON),
        ({"delay_off": 5}, STATE_ON, STATE_OFF, STATE_ON),
        ({"delay_off": 5}, STATE_ON, STATE_UNAVAILABLE, STATE_ON),
        ({"delay_off": 5}, STATE_ON, STATE_UNKNOWN, STATE_ON),
        ({"delay_on": 5}, STATE_ON, STATE_ON, STATE_ON),
        ({"delay_on": 5}, STATE_ON, STATE_OFF, STATE_OFF),
        ({"delay_on": 5}, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN),
        ({"delay_on": 5}, STATE_ON, STATE_UNKNOWN, STATE_UNKNOWN),
        ({}, None, STATE_ON, STATE_UNKNOWN),
        ({}, None, STATE_OFF, STATE_UNKNOWN),
        ({}, None, STATE_UNAVAILABLE, STATE_UNKNOWN),
        ({}, None, STATE_UNKNOWN, STATE_UNKNOWN),
        ({"delay_off": 5}, None, STATE_ON, STATE_UNKNOWN),
        ({"delay_off": 5}, None, STATE_OFF, STATE_UNKNOWN),
        ({"delay_off": 5}, None, STATE_UNAVAILABLE, STATE_UNKNOWN),
        ({"delay_off": 5}, None, STATE_UNKNOWN, STATE_UNKNOWN),
        ({"delay_on": 5}, None, STATE_ON, STATE_UNKNOWN),
        ({"delay_on": 5}, None, STATE_OFF, STATE_UNKNOWN),
        ({"delay_on": 5}, None, STATE_UNAVAILABLE, STATE_UNKNOWN),
        ({"delay_on": 5}, None, STATE_UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: ConfigType,
    source_state: str | None,
    restored_state: str,
    initial_state: str,
) -> None:
    """Test restoring template binary sensor."""

    hass.states.async_set(TEST_STATE_ENTITY_ID, source_state)
    await hass.async_block_till_done()

    fake_state = State(TEST_ENTITY_ID, restored_state, {})
    mock_restore_cache(hass, (fake_state,))

    await async_setup_binary_sensor(hass, count, style, state_template, extra_config)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == initial_state


@pytest.mark.parametrize(
    ("count", "style", "state_template", "extra_config"),
    [
        (
            1,
            ConfigurationStyle.TRIGGER,
            _BEER_TRIGGER_VALUE_TEMPLATE,
            {
                "device_class": "motion",
                "delay_on": '{{ ({ "seconds": 6 / 2 }) }}',
                "auto_off": '{{ ({ "seconds": 1 + 1 }) }}',
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("beer_count", "first_state", "second_state", "final_state"),
    [
        (2, STATE_UNKNOWN, STATE_ON, STATE_OFF),
        (1, STATE_OFF, STATE_OFF, STATE_OFF),
        (0, STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN),
        (-1, STATE_UNAVAILABLE, STATE_UNAVAILABLE, STATE_UNAVAILABLE),
    ],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_template_with_trigger_templated_auto_off(
    hass: HomeAssistant,
    beer_count: int,
    first_state: str,
    second_state: str,
    final_state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor template with template auto off."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": beer_count}, context=context)
    await hass.async_block_till_done()

    # State should still be unknown
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == first_state

    # Now wait for the on delay
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == second_state

    # Now wait for the auto-off
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == final_state


@pytest.mark.parametrize(
    ("count", "style", "state_template", "extra_config"),
    [
        (
            1,
            ConfigurationStyle.TRIGGER,
            _BEER_TRIGGER_VALUE_TEMPLATE,
            {
                "device_class": "motion",
                "delay_on": "00:00:02",
                "auto_off": "00:00:01",
            },
        )
    ],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_template_trigger_delay_on_and_auto_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor template with delay_on, auto_off, and multiple triggers."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    # State should still be unknown
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    last_state = STATE_UNKNOWN

    for _ in range(5):
        # Now wait and trigger again to test that the 2 second on_delay is not recreated
        freezer.tick(timedelta(seconds=1))
        hass.bus.async_fire("test_event", {"beer": 2}, context=context)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == last_state

        # Now wait for the on delay
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_ON

        # Now wait for the auto-off
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_OFF

        # Now wait to trigger again
        freezer.tick(timedelta(seconds=1))
        hass.bus.async_fire("test_event", {"beer": 2}, context=context)
        await hass.async_block_till_done()

        # State should still be off
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_OFF

        last_state = STATE_OFF


@pytest.mark.parametrize(
    ("count", "style", "state_template", "extra_config"),
    [
        (
            1,
            ConfigurationStyle.MODERN,
            "{{ states('binary_sensor.test_state') }}",
            {
                "device_class": "motion",
                "delay_on": "00:00:02",
            },
        )
    ],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_template_multiple_states_delay_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor template with delay_on and multiple state changes."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    # State should be off
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    for _ in range(5):
        # Now wait for the on delay
        freezer.tick(timedelta(seconds=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_ON

        freezer.tick(timedelta(seconds=1))
        hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=1))
        hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
        await hass.async_block_till_done()

        # State should still be off
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "style", "state_template", "extra_config"),
    [
        (
            1,
            ConfigurationStyle.TRIGGER,
            "{{ True }}",
            {
                "device_class": "motion",
                "auto_off": '{{ ({ "seconds": 5 }) }}',
            },
        )
    ],
)
@pytest.mark.usefixtures("setup_binary_sensor")
async def test_template_with_trigger_auto_off_cancel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor template with template auto off."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {}, context=context)
    await hass.async_block_till_done()

    # State should still be unknown
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    # Now wait for the on delay
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    hass.bus.async_fire("test_event", {}, context=context)
    await hass.async_block_till_done()

    # Now wait for the on delay
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    # Now wait for the auto-off
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "style", "extra_config", "attribute_value"),
    [
        (
            1,
            ConfigurationStyle.TRIGGER,
            {"device_class": "motion"},
            "{{ states('sensor.test_attribute') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("state_template", "attribute"),
    [
        ("{{ True }}", "delay_on"),
        ("{{ False }}", "delay_off"),
        ("{{ True }}", "auto_off"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_trigger_with_negative_time_periods(
    hass: HomeAssistant, attribute: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test binary sensor template with template negative time periods."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "-5")
    await hass.async_block_till_done()

    assert f"Error rendering {attribute} template: " in caplog.text


@pytest.mark.parametrize(
    ("count", "style", "extra_config", "attribute_value"),
    [
        (
            1,
            ConfigurationStyle.TRIGGER,
            {"device_class": "motion"},
            "{{ ({ 'seconds': 10 }) }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("state_template", "attribute", "delay_state"),
    [
        ("{{ trigger.event.data.beer == 2 }}", "delay_on", STATE_ON),
        ("{{ trigger.event.data.beer != 2 }}", "delay_off", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_binary_sensor")
async def test_trigger_template_delay_with_multiple_triggers(
    hass: HomeAssistant, delay_state: str, freezer: FrozenDateTimeFactory
) -> None:
    """Test trigger based binary sensor with multiple triggers occurring during the delay."""
    for _ in range(10):
        # State should still be unknown
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == STATE_UNKNOWN

        hass.bus.async_fire("test_event", {"beer": 2}, context=Context())
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == delay_state


@pytest.mark.parametrize(
    ("restored_state", "initial_state", "initial_attributes"),
    [
        (STATE_ON, STATE_ON, ["entity_picture", "icon", "plus_one"]),
        (STATE_OFF, STATE_OFF, ["entity_picture", "icon", "plus_one"]),
        (STATE_UNAVAILABLE, STATE_UNKNOWN, []),
        (STATE_UNKNOWN, STATE_UNKNOWN, []),
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    restored_state: str,
    initial_state: str,
    initial_attributes: list[str],
) -> None:
    """Test restoring trigger template binary sensor."""

    restored_attributes = {
        "entity_picture": "/local/cats.png",
        "icon": "mdi:ship",
        "plus_one": 55,
    }

    fake_state = State(
        TEST_ENTITY_ID,
        restored_state,
        restored_attributes,
    )
    fake_extra_data = {
        "auto_off_time": None,
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        _BEER_TRIGGER_VALUE_TEMPLATE,
        {
            "device_class": "motion",
            "picture": "{{ '/local/dogs.png' }}",
            "icon": "{{ 'mdi:pirate' }}",
            "attributes": {
                "plus_one": "{{ trigger.event.data.beer + 1 }}",
                "another": "{{ trigger.event.data.uno_mas or 1 }}",
            },
        },
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == initial_state
    for attr, value in restored_attributes.items():
        if attr in initial_attributes:
            assert state.attributes[attr] == value
        else:
            assert attr not in state.attributes
    assert "another" not in state.attributes

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["icon"] == "mdi:pirate"
    assert state.attributes["entity_picture"] == "/local/dogs.png"
    assert state.attributes["plus_one"] == 3
    assert state.attributes["another"] == 1


@pytest.mark.parametrize("restored_state", [STATE_ON, STATE_OFF])
async def test_trigger_entity_restore_state_auto_off(
    hass: HomeAssistant,
    restored_state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test restoring trigger template binary sensor."""

    freezer.move_to("2022-02-02 12:02:00+00:00")
    fake_state = State(TEST_ENTITY_ID, restored_state, {})
    fake_extra_data = {
        "auto_off_time": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2022, 2, 2, 12, 2, 2, tzinfo=UTC).isoformat(),
        },
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        _BEER_TRIGGER_VALUE_TEMPLATE,
        {"device_class": "motion", "auto_off": '{{ ({ "seconds": 1 + 1 }) }}'},
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == restored_state

    # Now wait for the auto-off
    freezer.move_to("2022-02-02 12:02:03+00:00")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_trigger_entity_restore_state_auto_off_expired(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test restoring trigger template binary sensor."""

    freezer.move_to("2022-02-02 12:02:00+00:00")
    fake_state = State(TEST_ENTITY_ID, STATE_ON, {})
    fake_extra_data = {
        "auto_off_time": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2022, 2, 2, 12, 2, 0, tzinfo=UTC).isoformat(),
        },
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        _BEER_TRIGGER_VALUE_TEMPLATE,
        {"device_class": "motion", "auto_off": '{{ ({ "seconds": 1 + 1 }) }}'},
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_saving_auto_off(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we restore state integration."""
    restored_attributes = {
        "entity_picture": "/local/cats.png",
        "icon": "mdi:ship",
        "plus_one": 55,
    }

    freezer.move_to("2022-02-02 02:02:00+00:00")
    fake_extra_data = {
        "auto_off_time": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": "2022-02-02T02:02:02+00:00",
        },
    }
    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        "{{ True }}",
        {
            "device_class": "motion",
            "auto_off": '{{ ({ "seconds": 1 + 1 }) }}',
            "attributes": restored_attributes,
        },
    )

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == TEST_ENTITY_ID

    for attr, value in restored_attributes.items():
        assert state["attributes"][attr] == value

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == fake_extra_data


async def test_trigger_entity_restore_invalid_auto_off_time_data(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test restoring trigger template binary sensor."""

    freezer.move_to("2022-02-02 12:02:00+00:00")
    fake_state = State(TEST_ENTITY_ID, STATE_ON, {})
    fake_extra_data = {
        "auto_off_time": {
            "_type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2022, 2, 2, 12, 2, 0, tzinfo=UTC).isoformat(),
        },
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    await async_mock_restore_state_shutdown_restart(hass)

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == fake_extra_data

    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        _BEER_TRIGGER_VALUE_TEMPLATE,
        {"device_class": "motion", "auto_off": '{{ ({ "seconds": 1 + 1 }) }}'},
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN


async def test_trigger_entity_restore_invalid_auto_off_time_key(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test restoring trigger template binary sensor."""

    freezer.move_to("2022-02-02 12:02:00+00:00")
    fake_state = State(TEST_ENTITY_ID, STATE_ON, {})
    fake_extra_data = {
        "auto_off_timex": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2022, 2, 2, 12, 2, 0, tzinfo=UTC).isoformat(),
        },
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))
    await async_mock_restore_state_shutdown_restart(hass)

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert "auto_off_timex" in extra_data
    assert extra_data == fake_extra_data

    await async_setup_binary_sensor(
        hass,
        1,
        ConfigurationStyle.TRIGGER,
        _BEER_TRIGGER_VALUE_TEMPLATE,
        {"device_class": "motion", "auto_off": '{{ ({ "seconds": 1 + 1 }) }}'},
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN


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
        identifiers={("sensor", "identifier_test")},
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
            "state": "{{10 > 8}}",
            "template_type": "binary_sensor",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("binary_sensor.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


async def test_flow_preview(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the config flow preview."""
    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        binary_sensor.DOMAIN,
        {"name": "My template", "state": "{{ 'on' }}"},
    )
    assert state["state"] == "on"
