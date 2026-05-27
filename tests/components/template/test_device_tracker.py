"""The tests for the Template device_tracker platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import device_tracker, template, zone
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

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

from tests.common import MockConfigEntry, async_setup_component
from tests.conftest import WebSocketGenerator

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_LATITUDE_ENTITY_ID = "sensor.test_latitude"
TEST_LONGITUDE_ENTITY_ID = "sensor.test_longitude"
TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.availability"
TEST_TRACKER = TemplatePlatformSetup(
    device_tracker.DOMAIN,
    "template_device_tracker",
    make_test_trigger(
        TEST_AVAILABILITY_ENTITY_ID,
        TEST_LATITUDE_ENTITY_ID,
        TEST_LONGITUDE_ENTITY_ID,
        TEST_STATE_ENTITY_ID,
    ),
)

TEST_MINIMUM_REQUIREMENTS = {
    "latitude": "{{ 10 }}",
    "longitude": "{{ 40 }}",
}
TEST_TRACKER_CONFIG = {
    "latitude": "{{ states('sensor.test_latitude') }}",
    "longitude": "{{ states('sensor.test_longitude') }}",
}


async def setup_zones(hass: HomeAssistant) -> None:
    """Set up zone integration."""
    assert await async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": [
                {"name": "Home", "latitude": 32.87336, "longitude": -117.22743},
                {
                    "name": "Work",
                    "latitude": 32.8768333,
                    "longitude": -117.2273295,
                    "radius": 250,
                },
            ]
        },
    )
    assert len(hass.states.async_entity_ids("zone")) == 2


@pytest.fixture
async def setup_tracker(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of device_tracker integration."""
    await setup_zones(hass)
    await setup_entity(hass, TEST_TRACKER, style, 1, config, extra_config=extra_config)


@pytest.fixture
async def setup_single_attribute_tracker(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of device_tracker integration testing a single attribute."""
    await setup_zones(hass)
    await setup_entity(
        hass,
        TEST_TRACKER,
        style,
        1,
        config,
        extra_config={attribute: attribute_template}
        if attribute and attribute_template
        else {},
    )


@pytest.mark.parametrize(
    "config",
    [
        {"latitude": "{{ 10 }}"},
        {"longitude": "{{ 10 }}"},
        {"in_zones": "{{ ['zone.home'] }}", "latitude": "{{ 10 }}"},
        {"in_zones": "{{ ['zone.home'] }}", "longitude": "{{ 10 }}"},
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_required_keys(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test that required keys are present."""
    await setup_entity(hass, TEST_TRACKER, style, 0, config)
    assert hass.states.async_all("device_tracker") == []


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "anything",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": TEST_TRACKER.object_id,
            **TEST_MINIMUM_REQUIREMENTS,
            "advanced_options": {"location_accuracy": "{{ 10 }}"},
            "template_type": device_tracker.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state is not None
    assert state == snapshot


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
            **TEST_MINIMUM_REQUIREMENTS,
            "template_type": "device_tracker",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("device_tracker.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(
    ("config", "extra_config"),
    [
        ({"latitude": "{{ 10 }}", "longitude": "{{states.test['big.fat...']}}"}, None),
        ({"latitude": "{{states.test['big.fat...']}}", "longitude": "{{ 10 }}"}, None),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_tracker")
async def test_syntax_error(hass: HomeAssistant) -> None:
    """Test template latitude and longitude with render error."""
    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("config", "attribute"),
    [({}, "in_zones")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected_value", "expected_state"),
    [
        ("{{ [] }}", [], STATE_NOT_HOME),
        ("{{ ['zone.home'] }}", ["zone.home"], STATE_HOME),
        (
            "{{ ['zone.work'] }}",
            ["zone.work"],
            "Work",
        ),
        (
            "{{ ['zone.home', 'zone.work'] }}",
            ["zone.home", "zone.work"],
            STATE_HOME,
        ),
        (
            "{{ ['zone.work', 'zone.home'] }}",
            ["zone.home", "zone.work"],
            STATE_HOME,
        ),
        ("{{ ['zone.something'] }}", [], STATE_NOT_HOME),
        ("{{ ['sensor.something'] }}", [], STATE_NOT_HOME),
        ("{{ ['not_an_entity_id'] }}", [], STATE_NOT_HOME),
        ("{{ None }}", [], STATE_UNKNOWN),
        ("{{ 110 }}", [], STATE_UNKNOWN),
        ("{{ -110 }}", [], STATE_UNKNOWN),
        ("{{ 'on' }}", [], STATE_UNKNOWN),
        ("{{ x - 1 }}", [], STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_in_zones(
    hass: HomeAssistant,
    attribute: str,
    expected_value: list[str] | None,
    expected_state: str,
) -> None:
    """Test template in_zones."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == expected_state
    assert state.attributes.get(attribute) == expected_value


@pytest.mark.parametrize(
    ("config", "attribute"),
    [({}, "in_zones")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected_state", "error"),
    [
        (
            "{{ ['sensor.something'] }}",
            STATE_NOT_HOME,
            "Received invalid device_tracker in_zones: "
            "['sensor.something'] for entity device_tracker.template_device_tracker, "
            "expected a list of zone entity_ids",
        ),
        (
            "{{ ['not_an_entity_id'] }}",
            STATE_NOT_HOME,
            "Received invalid device_tracker in_zones: "
            "['not_an_entity_id'] for entity device_tracker.template_device_tracker, "
            "expected a list of zone entity_ids",
        ),
        (
            "{{ -110 }}",
            STATE_UNKNOWN,
            "Received invalid device_tracker in_zones: "
            "-110 for entity device_tracker.template_device_tracker, "
            "expected a list of zone entity_ids",
        ),
        (
            "{{ 'on' }}",
            STATE_UNKNOWN,
            "Received invalid device_tracker in_zones: "
            "on for entity device_tracker.template_device_tracker, "
            "expected a list of zone entity_ids",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_in_zones_creates_error(
    hass: HomeAssistant,
    expected_state: str,
    error: str,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text: str,
) -> None:
    """Test template latitude."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == expected_state
    assert state.attributes["in_zones"] == []

    assert error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    ("config", "attribute"),
    [({"longitude": "{{ 10 }}"}, "latitude")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected_value", "expected_state"),
    [
        ("{{ -90 }}", -90.0, STATE_NOT_HOME),
        ("{{ 1 }}", 1.0, STATE_NOT_HOME),
        ("{{ 42 }}", 42.0, STATE_NOT_HOME),
        ("{{ 90 }}", 90.0, STATE_NOT_HOME),
        ("{{ None }}", None, STATE_UNKNOWN),
        ("{{ 110 }}", None, STATE_UNKNOWN),
        ("{{ -110 }}", None, STATE_UNKNOWN),
        ("{{ 'on' }}", None, STATE_UNKNOWN),
        ("{{ x - 1 }}", None, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_latitude(
    hass: HomeAssistant,
    attribute: str,
    expected_value: float | None,
    expected_state: str,
) -> None:
    """Test template latitude."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == expected_state
    assert state.attributes.get(attribute) == expected_value


@pytest.mark.parametrize(
    ("config", "attribute"),
    [({"latitude": "{{ 10 }}"}, "longitude")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected_value", "expected_state"),
    [
        ("{{ -180 }}", -180.0, STATE_NOT_HOME),
        ("{{ 1 }}", 1.0, STATE_NOT_HOME),
        ("{{ 42 }}", 42.0, STATE_NOT_HOME),
        ("{{ 180 }}", 180.0, STATE_NOT_HOME),
        ("{{ None }}", None, STATE_UNKNOWN),
        ("{{ 181 }}", None, STATE_UNKNOWN),
        ("{{ -181 }}", None, STATE_UNKNOWN),
        ("{{ 'on' }}", None, STATE_UNKNOWN),
        ("{{ x - 1 }}", None, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_longitude(
    hass: HomeAssistant,
    attribute: str,
    expected_value: float | None,
    expected_state: str,
) -> None:
    """Test template longitude."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == expected_state
    assert state.attributes.get(attribute) == expected_value


@pytest.mark.parametrize(
    ("config", "attribute", "state_attribute"),
    [
        (
            {"latitude": "{{ 10 }}", "longitude": "{{ 10 }}"},
            "location_accuracy",
            "gps_accuracy",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected_value"),
    [
        ("{{ 0 }}", 0.0),
        ("{{ 1 }}", 1.0),
        ("{{ 50 }}", 50.0),
        ("{{ 500 }}", 500.0),
        ("{{ None }}", 0.0),
        ("{{ -1 }}", 0.0),
        ("{{ 'on' }}", 0.0),
        ("{{ x - 1 }}", 0.0),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_location_accuracy(
    hass: HomeAssistant,
    expected_value: float | None,
    state_attribute: str,
) -> None:
    """Test template location_accuracy."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[state_attribute] == expected_value


@pytest.mark.parametrize("config", [TEST_MINIMUM_REQUIREMENTS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute", "attribute_template", "key", "expected"),
    [
        (
            "picture",
            "{% if is_state('sensor.test_state', 'on') %}something{% endif %}",
            ATTR_ENTITY_PICTURE,
            "something",
        ),
        (
            "icon",
            "{% if is_state('sensor.test_state', 'on') %}mdi:something{% endif %}",
            ATTR_ICON,
            "mdi:something",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_entity_picture_and_icon_templates(
    hass: HomeAssistant, key: str, expected: str
) -> None:
    """Test picture and icon template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "off")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.attributes.get(key) == ""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "on")

    state = hass.states.get(TEST_TRACKER.entity_id)

    assert state.attributes[key] == expected


@pytest.mark.parametrize(
    ("config", "extra_config"),
    [
        (
            {
                "latitude": "{{ state_attr('sensor.test_state', 'latitude') }}",
                "longitude": "{{ state_attr('sensor.test_state', 'longitude') }}",
            },
            {},
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_tracker")
async def test_template_updates(hass: HomeAssistant) -> None:
    """Test template device_tracker updates with entity."""
    await async_trigger(
        hass, TEST_STATE_ENTITY_ID, "anything", {"latitude": 10.0, "longitude": 10.0}
    )

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == STATE_NOT_HOME
    assert state.attributes["latitude"] == 10.0
    assert state.attributes["longitude"] == 10.0

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "anything",
        {"latitude": 32.87336, "longitude": -117.22743},
    )

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == STATE_HOME
    assert state.attributes["latitude"] == 32.87336
    assert state.attributes["longitude"] == -117.22743


@pytest.mark.parametrize(
    ("config", "attribute", "attribute_template"),
    [
        (
            TEST_TRACKER_CONFIG,
            "availability",
            "{{ is_state('binary_sensor.availability', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    await async_trigger(hass, TEST_LATITUDE_ENTITY_ID, 10.0)
    await async_trigger(hass, TEST_LONGITUDE_ENTITY_ID, 10.0)
    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "on")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["latitude"] == 10.0
    assert state.attributes["longitude"] == 10.0

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "off")

    state = hass.states.get(TEST_TRACKER.entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert "latitude" not in state.attributes
    assert "longitude" not in state.attributes


@pytest.mark.parametrize(
    ("config", "attribute", "attribute_template"),
    [
        (
            TEST_MINIMUM_REQUIREMENTS,
            "availability",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_tracker")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text,
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    assert hass.states.get(TEST_TRACKER.entity_id).state != STATE_UNAVAILABLE

    error = "UndefinedError: 'x' is undefined"
    assert error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test unique_id option only creates one device_tracker per id."""
    await setup_and_test_unique_id(hass, TEST_TRACKER, style, TEST_MINIMUM_REQUIREMENTS)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to device_tracker unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_TRACKER, style, entity_registry, TEST_MINIMUM_REQUIREMENTS
    )


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        device_tracker.DOMAIN,
        {"name": "My template", **TEST_MINIMUM_REQUIREMENTS},
    )

    assert state["state"] == STATE_NOT_HOME
    assert state["attributes"]["latitude"] == 10.0
    assert state["attributes"]["longitude"] == 40.0
