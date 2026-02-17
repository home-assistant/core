"""The test for the Template sensor platform."""

from asyncio import Event
from datetime import datetime
from unittest.mock import ANY, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.bootstrap import async_from_config_dict
from homeassistant.components import sensor, template
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import ATTR_COMPONENT, async_setup_component
from homeassistant.util import dt as dt_util

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
    async_capture_events,
    mock_restore_cache_with_extra_data,
)
from tests.conftest import WebSocketGenerator

TEST_STATE_SENSOR = "sensor.test_state"
TEST_AVAILABILITY_SENSOR = "sensor.availability_sensor"

TEST_SENSOR = TemplatePlatformSetup(
    sensor.DOMAIN,
    "sensors",
    "test_template_sensor",
    make_test_trigger(TEST_STATE_SENSOR, TEST_AVAILABILITY_SENSOR),
)


@pytest.fixture
async def setup_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Do setup of sensor integration."""
    await setup_entity(hass, TEST_SENSOR, style, count, config)


@pytest.fixture
async def setup_state_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    config: ConfigType,
) -> None:
    """Do setup of sensor integration using a state template."""
    await setup_entity(hass, TEST_SENSOR, style, count, config, state_template)


@pytest.fixture
async def setup_single_attribute_state_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of sensor integration testing a single attribute."""
    config = {attribute: attribute_template} if attribute and attribute_template else {}
    await setup_entity(
        hass,
        TEST_SENSOR,
        style,
        count,
        config,
        state_template,
        extra_config,
    )


@pytest.fixture
async def setup_attributes_state_sensor(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    attributes: dict,
) -> None:
    """Do setup of sensor integration testing a single attribute."""
    await setup_entity(
        hass,
        TEST_SENSOR,
        style,
        count,
        {},
        state_template,
        attributes=attributes,
    )


@pytest.mark.parametrize(
    "config_entry_extra_options",
    [
        {},
        {
            "device_class": "battery",
            "state_class": "measurement",
            "unit_of_measurement": "%",
        },
    ],
)
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry_extra_options: dict[str, str],
) -> None:
    """Test the config flow."""
    state_template = "{{ float(states('sensor.one')) + float(states('sensor.two')) }}"
    input_entities = ["one", "two"]
    input_states = {"one": "10", "two": "20"}
    template_type = sensor.DOMAIN

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


@pytest.mark.parametrize(
    ("count", "config", "state_template"),
    [(1, {}, "It {{ states.sensor.test_state.state }}.")],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.LEGACY, "It ."),
        (ConfigurationStyle.MODERN, "It ."),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_state_sensor")
async def test_sensor_state(hass: HomeAssistant, initial_state: str) -> None:
    """Test template."""
    assert hass.states.get(TEST_SENSOR.entity_id).state == initial_state

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    assert hass.states.get(TEST_SENSOR.entity_id).state == "It Works."


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template"),
    [(1, {}, "{{ states('sensor.test_state') }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "icon_template"),
        (ConfigurationStyle.MODERN, "icon"),
        (ConfigurationStyle.TRIGGER, "icon"),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "before_update", "after_update"),
    [
        (
            "{{ 'mdi:check' if is_state('sensor.test_state', 'Works') else '' }}",
            "",
            "mdi:check",
        ),
        (
            "{{ 'mdi:check' }}",
            "mdi:check",
            "mdi:check",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_icon_template(
    hass: HomeAssistant, before_update: str | None, after_update: str | None
) -> None:
    """Test icon template."""
    await async_trigger(hass, TEST_STATE_SENSOR, "")
    assert hass.states.get(TEST_SENSOR.entity_id).attributes["icon"] == before_update

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    assert hass.states.get(TEST_SENSOR.entity_id).attributes["icon"] == after_update


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template"),
    [(1, {}, "{{ states('sensor.test_state') }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template"),
        (ConfigurationStyle.MODERN, "picture"),
        (ConfigurationStyle.TRIGGER, "picture"),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "before_update", "after_update"),
    [
        (
            "{{ '/local/sensor.png' if is_state('sensor.test_state', 'Works') else '' }}",
            "",
            "/local/sensor.png",
        ),
        (
            "{{ '/local/sensor.png' }}",
            "/local/sensor.png",
            "/local/sensor.png",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_entity_picture_template(
    hass: HomeAssistant, before_update: str | None, after_update: str | None
) -> None:
    """Test entity_picture template."""
    await async_trigger(hass, TEST_STATE_SENSOR, "")
    assert (
        hass.states.get(TEST_SENSOR.entity_id).attributes["entity_picture"]
        == before_update
    )

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    assert (
        hass.states.get(TEST_SENSOR.entity_id).attributes["entity_picture"]
        == after_update
    )


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template"),
    [(1, {}, "{{ states('sensor.test_state') }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute", "entity_id"),
    [
        (ConfigurationStyle.LEGACY, "friendly_name_template", TEST_SENSOR.entity_id),
        (ConfigurationStyle.MODERN, "name", TEST_SENSOR.entity_id),
        (ConfigurationStyle.TRIGGER, "name", "sensor.unnamed_device"),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "after_update"),
    [
        (
            "{{ 'It Works.' if is_state('sensor.test_state', 'Works') else 'test_template_sensor' }}",
            "It Works.",
        ),
        (
            "{{ 'test_template_sensor' }}",
            "test_template_sensor",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_name_template(
    hass: HomeAssistant, entity_id: str, after_update: str | None
) -> None:
    """Test friendly_name template with an unknown value_template."""
    await async_trigger(hass, TEST_STATE_SENSOR, "")
    assert (
        hass.states.get(entity_id).attributes["friendly_name"] == TEST_SENSOR.object_id
    )

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    assert hass.states.get(entity_id).attributes["friendly_name"] == after_update


@pytest.mark.parametrize(("count", "domain"), [(0, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {"value_template": "{% if rubbish %}"}
                },
            },
        },
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test INVALID sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}"
                    }
                },
            },
        },
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {"invalid"},
                },
            },
        },
        {
            "sensor": {
                "platform": "template",
            },
        },
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "not_value_template": "{{ states.sensor.test_state.state }}"
                    }
                },
            },
        },
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "test": {
                            "value_template": "{{ states.sensor.test_sensor.state }}",
                            "device_class": "foobarnotreal",
                        }
                    }
                },
            },
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_legacy_template_syntax_error(hass: HomeAssistant) -> None:
    """Test setup with invalid device_class."""
    assert hass.states.async_all("sensor") == []


@pytest.mark.parametrize(
    ("count", "config", "state_template"),
    [(1, {}, "{{ x - 12 }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_sensor")
async def test_bad_template_unavailable(hass: HomeAssistant) -> None:
    """Test a bad template creates an unavailable sensor."""
    await async_trigger(hass, TEST_STATE_SENSOR)
    assert hass.states.get(TEST_SENSOR.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "state_template"),
    [(1, "{{ states('sensor.test_sensor') | float(0) }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("config", "expected_device_class"),
    [
        (
            {
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
            "temperature",
        ),
        (
            {},
            None,
        ),
    ],
)
@pytest.mark.usefixtures("setup_state_sensor")
async def test_setup_valid_device_class(
    hass: HomeAssistant, expected_device_class: str | None
) -> None:
    """Test setup with valid device_class."""
    await async_trigger(hass, TEST_STATE_SENSOR, "75")
    assert (
        hass.states.get(TEST_SENSOR.entity_id).attributes.get("device_class")
        == expected_device_class
    )


@pytest.mark.parametrize("load_registries", [False])
async def test_creating_sensor_loads_group(hass: HomeAssistant) -> None:
    """Test setting up template sensor loads group component first."""
    order = []
    after_dep_event = Event()

    async def async_setup_group(hass: HomeAssistant, config: ConfigType) -> bool:
        # Make sure group takes longer to load, so that it won't
        # be loaded first by chance
        await after_dep_event.wait()

        order.append("group")
        return True

    async def async_setup_template(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddConfigEntryEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> bool:
        order.append("sensor.template")
        return True

    async def set_after_dep_event(event):
        if event.data[ATTR_COMPONENT] == "sensor":
            after_dep_event.set()

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, set_after_dep_event)

    with (
        patch(
            "homeassistant.components.group.async_setup",
            new=async_setup_group,
        ),
        patch(
            "homeassistant.components.template.sensor.async_setup_platform",
            new=async_setup_template,
        ),
    ):
        await async_from_config_dict(
            {
                "template": [{"sensor": {"name": "foo", "state": "{{ 'bar' }}"}}],
                "group": {},
            },
            hass,
        )
        await hass.async_block_till_done()

    assert order == ["group", "sensor.template"]


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template", "attribute_template"),
    [
        (
            1,
            {},
            "{{ states('sensor.test_state') }}",
            "{{ is_state('sensor.availability_sensor', 'on') }}",
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
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability tempalates with values from other entities."""
    # When template returns true..
    await async_trigger(hass, TEST_AVAILABILITY_SENSOR, STATE_ON)

    # Device State should not be unavailable
    assert hass.states.get(TEST_SENSOR.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    await async_trigger(hass, TEST_AVAILABILITY_SENSOR, STATE_OFF)

    # device state should be unavailable
    assert hass.states.get(TEST_SENSOR.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template", "attribute_template"),
    [
        (
            1,
            {},
            "{{ 'something' }}",
            "{{ x - 12 }}",
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
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_SENSOR)
    assert hass.states.get(TEST_SENSOR.entity_id) != STATE_UNAVAILABLE
    err = "'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("count", "state_template", "attributes", "before", "after"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            {"test_attribute": "It {{ states('sensor.test_state') }}."},
            "It .",
            "It Works.",
        ),
        (
            1,
            "{{ states('sensor.test_state') }}",
            {"test_attribute": "{{ 'It static' }}."},
            "It static.",
            "It static.",
        ),
    ],
)
@pytest.mark.usefixtures("setup_attributes_state_sensor")
async def test_attribute_templates(
    hass: HomeAssistant, before: str, after: str
) -> None:
    """Test attribute_templates template."""
    await async_trigger(hass, TEST_STATE_SENSOR, "")
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state.attributes["test_attribute"] == before

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    await async_update_entity(hass, TEST_SENSOR.entity_id)
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state.attributes["test_attribute"] == after


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    ("count", "state_template", "attributes"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            {"test_attribute": "{{ states.sensor.unknown.attributes.picture }}"},
        )
    ],
)
@pytest.mark.usefixtures("setup_attributes_state_sensor")
async def test_invalid_attribute_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, caplog_setup_text
) -> None:
    """Test that errors are logged if rendering template fails."""
    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    error = (
        "Template variable error: 'None' has no attribute 'attributes' when rendering"
    )
    assert error in caplog.text or error in caplog_setup_text
    assert hass.states.get(TEST_SENSOR.entity_id).state == "Works"


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
) -> None:
    """Test unique_id option only creates one vacuum per id."""
    await setup_and_test_unique_id(hass, TEST_SENSOR, style, {}, "{{ 'foo' }}")


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
        hass, TEST_SENSOR, style, entity_registry, {}, "{{ 'foo' }}"
    )


@pytest.mark.parametrize(("count", "domain"), [(1, template.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "sensor": [
                    {
                        "name": "solar_angle",
                        "unit_of_measurement": "degrees",
                        "state": "{{ state_attr('sun.sun', 'elevation') }}",
                    },
                    {
                        "name": "sunrise",
                        "state": "{{ state_attr('sun.sun', 'next_rising') }}",
                    },
                ],
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_sun_renders_once_per_sensor(hass: HomeAssistant) -> None:
    """Test sun change renders the template only once per sensor."""

    now = dt_util.utcnow()
    hass.states.async_set(
        "sun.sun", "above_horizon", {"elevation": 45.3, "next_rising": now}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.solar_angle").state == "45.3"
    assert hass.states.get("sensor.sunrise").state == str(now)

    async_render_calls = []

    @callback
    def _record_async_render(self, *args, **kwargs):
        """Catch async_render."""
        async_render_calls.append(self.template)
        return "75"

    later = dt_util.utcnow()

    with patch.object(Template, "async_render", _record_async_render):
        hass.states.async_set("sun.sun", {"elevation": 50, "next_rising": later})
        await hass.async_block_till_done()

    assert hass.states.get("sensor.solar_angle").state == "75.0"
    assert hass.states.get("sensor.sunrise").state == "75"

    assert len(async_render_calls) == 2
    assert set(async_render_calls) == {
        "{{ state_attr('sun.sun', 'elevation') }}",
        "{{ state_attr('sun.sun', 'next_rising') }}",
    }


@pytest.mark.parametrize(
    ("style", "before", "after"),
    [
        (
            ConfigurationStyle.LEGACY,
            "It: " + TEST_SENSOR.entity_id,
            "Works: " + TEST_SENSOR.entity_id,
        ),
        (
            ConfigurationStyle.MODERN,
            "It: " + TEST_SENSOR.entity_id,
            "Works: " + TEST_SENSOR.entity_id,
        ),
        (
            # Trigger based template entities only resolve when triggered
            # therefore the templates will be 1 resolution behind when
            # dealing with the this object
            ConfigurationStyle.TRIGGER,
            ": " + TEST_SENSOR.entity_id,
            "It: " + TEST_SENSOR.entity_id,
        ),
    ],
)
@pytest.mark.parametrize(
    ("count", "state_template", "attributes"),
    [
        (
            1,
            "{{ this.attributes.test }}: {{ this.entity_id }}",
            {"test": "{{ states('sensor.test_state') }}"},
        ),
    ],
)
@pytest.mark.usefixtures("setup_attributes_state_sensor")
async def test_this_variable(hass: HomeAssistant, before: str, after: str) -> None:
    """Test this variable."""
    await async_trigger(hass, TEST_STATE_SENSOR, "It")
    await hass.async_block_till_done()
    assert hass.states.get(TEST_SENSOR.entity_id).state == before

    await async_trigger(hass, TEST_STATE_SENSOR, "Works")
    await hass.async_block_till_done()
    assert hass.states.get(TEST_SENSOR.entity_id).state == after


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "sensor": {
                    "state": "{{ this.attributes.get('test', 'no-test!') }}: {{ this.entity_id }}",
                    "icon": "mdi:{% if this.entity_id in states and 'friendly_name' in this.attributes %} {{this.attributes['friendly_name']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "name": "{% if this.entity_id in states and 'friendly_name' in this.attributes %} {{this.attributes['friendly_name']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "picture": "{% if this.entity_id in states and 'entity_picture' in this.attributes %} {{this.attributes['entity_picture']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "attributes": {"test": "{{ this.entity_id }}"},
                },
            },
        },
    ],
)
async def test_this_variable_early_hass_not_running(
    hass: HomeAssistant, config, count, domain
) -> None:
    """Test referencing 'this' variable before the entity is in the state machine.

    Hass is not yet started when the entity is added.
    Icon, name and picture templates are rendered once in the constructor.
    """
    entity_id = "sensor.none_false"

    hass.set_state(CoreState.not_running)

    # Setup template
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Sensor state not rendered, icon, name and picture
    # templates rendered in constructor with entity_id set to None
    state = hass.states.get(entity_id)
    assert state.state == "unknown"
    assert state.attributes == {
        "entity_picture": "None:False",
        "friendly_name": "None:False",
        "icon": "mdi:None:False",
    }

    # Signal hass started
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # icon, name, picture + other templates now re-rendered
    state = hass.states.get(entity_id)
    assert state.state == "sensor.none_false: sensor.none_false"
    assert state.attributes == {
        "entity_picture": "sensor.none_false:False",
        "friendly_name": "sensor.none_false:False",
        "icon": "mdi:sensor.none_false:False",
        "test": "sensor.none_false",
    }


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "sensor": {
                    "state": "{{ this.attributes.get('test', 'no-test!') }}: {{ this.entity_id }}",
                    "icon": "mdi:{% if this.entity_id in states and 'friendly_name' in this.attributes %} {{this.attributes['friendly_name']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "name": "{% if this.entity_id in states and 'friendly_name' in this.attributes %} {{this.attributes['friendly_name']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "picture": "{% if this.entity_id in states and 'entity_picture' in this.attributes %} {{this.attributes['entity_picture']}} {% else %}{{this.entity_id}}:{{this.entity_id in states}}{% endif %}",
                    "attributes": {"test": "{{ this.entity_id }}"},
                },
            },
        },
    ],
)
async def test_this_variable_early_hass_running(
    hass: HomeAssistant, config, count, domain
) -> None:
    """Test referencing 'this' variable before the entity is in the state machine.

    Hass is already started when the entity is added.
    Icon, name and picture templates are rendered in the constructor, and again
    before the entity is added to hass.
    """

    # Start hass
    assert hass.state is CoreState.running
    await hass.async_start()
    await hass.async_block_till_done()

    # Setup template
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    entity_id = "sensor.none_false"
    # All templated rendered
    state = hass.states.get(entity_id)
    assert state.state == "sensor.none_false: sensor.none_false"
    assert state.attributes == {
        "entity_picture": "sensor.none_false:False",
        "friendly_name": "sensor.none_false:False",
        "icon": "mdi:sensor.none_false:False",
        "test": "sensor.none_false",
    }


@pytest.mark.parametrize(
    ("count", "config", "state_template"),
    [(1, {}, "{{ ((states.sensor.test_template_sensor.state or 0) | int) + 1 }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
@pytest.mark.usefixtures("setup_state_sensor")
async def test_self_referencing_sensor_loop(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test a self referencing sensor does not loop forever."""
    assert len(hass.states.async_all()) == 1
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Template loop detected" in caplog_setup_text
    assert int(hass.states.get(TEST_SENSOR.entity_id).state) == 2
    await hass.async_block_till_done()
    assert int(hass.states.get(TEST_SENSOR.entity_id).state) == 2


@pytest.mark.parametrize(("count", "style"), [(1, ConfigurationStyle.MODERN)])
@pytest.mark.parametrize(
    ("config", "attributes", "expected_state"),
    [
        (
            {
                "state": "{{ ((states.sensor.test_template_sensor.state or 0) | int) + 1 }}",
                "icon": "{% if ((states.sensor.test_template_sensor.state or 0) | int) >= 1 %}mdi:greater{% else %}mdi:less{% endif %}",
            },
            ((ATTR_ICON, "mdi:greater"),),
            3,
        ),
        (
            {
                "state": "{{ ((states.sensor.test_template_sensor.state or 0) | int) + 1 }}",
                "icon": "{% if ((states.sensor.test_template_sensor.state or 0) | int) > 3 %}mdi:greater{% else %}mdi:less{% endif %}",
                "picture": "{% if ((states.sensor.test_template_sensor.state or 0) | int) >= 1 %}bigpic{% else %}smallpic{% endif %}",
            },
            (
                (ATTR_ICON, "mdi:less"),
                (ATTR_ENTITY_PICTURE, "bigpic"),
            ),
            4,
        ),
        (
            {
                "default_entity_id": TEST_SENSOR.entity_id,
                "state": "{{ 1 }}",
                "picture": "{{ ((states.sensor.test_template_sensor.attributes['entity_picture'] or 0) | int) + 1 }}",
                "name": "{{ ((states.sensor.test_template_sensor.attributes['friendly_name'] or 0) | int) + 1 }}",
            },
            (
                (ATTR_ENTITY_PICTURE, "3"),
                (ATTR_FRIENDLY_NAME, "3"),
            ),
            1,
        ),
    ],
)
@pytest.mark.usefixtures("setup_sensor")
async def test_self_referencing(
    hass: HomeAssistant,
    attributes: tuple[tuple[str, str]],
    expected_state: int,
    caplog_setup_text,
) -> None:
    """Test a self referencing sensor loops forever."""
    assert len(hass.states.async_all()) == 1
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Template loop detected" in caplog_setup_text

    state = hass.states.get(TEST_SENSOR.entity_id)
    assert int(state.state) == expected_state
    for attr, expected in attributes:
        assert state.attributes[attr] == expected
    await hass.async_block_till_done()
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert int(state.state) == expected_state


async def test_self_referencing_icon_with_no_loop(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a self referencing icon that does not loop."""

    hass.states.async_set("sensor.heartworm_high_80", 10)
    hass.states.async_set("sensor.heartworm_low_57", 10)
    hass.states.async_set("sensor.heartworm_avg_64", 10)
    hass.states.async_set("sensor.heartworm_avg_57", 10)

    value_template_str = """{% if (states.sensor.heartworm_high_80.state|int >= 10) and (states.sensor.heartworm_low_57.state|int >= 10) %}
            extreme
          {% elif (states.sensor.heartworm_avg_64.state|int >= 30) %}
            high
          {% elif (states.sensor.heartworm_avg_64.state|int >= 14) %}
            moderate
          {% elif (states.sensor.heartworm_avg_64.state|int >= 5) %}
            slight
          {% elif (states.sensor.heartworm_avg_57.state|int >= 5) %}
            marginal
          {% elif (states.sensor.heartworm_avg_57.state|int < 5) %}
            none
          {% endif %}"""

    icon_template_str = """{% if is_state('sensor.heartworm_risk',"extreme") %}
            mdi:hazard-lights
          {% elif is_state('sensor.heartworm_risk',"high") %}
            mdi:triangle-outline
          {% elif is_state('sensor.heartworm_risk',"moderate") %}
            mdi:alert-circle-outline
          {% elif is_state('sensor.heartworm_risk',"slight") %}
            mdi:exclamation
          {% elif is_state('sensor.heartworm_risk',"marginal") %}
            mdi:heart
          {% elif is_state('sensor.heartworm_risk',"none") %}
            mdi:snowflake
          {% endif %}"""

    await async_setup_component(
        hass,
        template.DOMAIN,
        {
            "template": [
                {
                    "sensor": [
                        {
                            "name": "heartworm_risk",
                            "state": value_template_str,
                            "icon": icon_template_str,
                        }
                    ],
                }
            ]
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5

    hass.states.async_set("sensor.heartworm_high_80", 10)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert "Template loop detected" not in caplog.text

    state = hass.states.get("sensor.heartworm_risk")
    assert state.state == "extreme"
    assert state.attributes[ATTR_ICON] == "mdi:hazard-lights"

    await hass.async_block_till_done()
    assert state.state == "extreme"
    assert state.attributes[ATTR_ICON] == "mdi:hazard-lights"
    assert "Template loop detected" not in caplog.text


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template", "attribute", "attribute_template"),
    [
        (
            1,
            {"default_entity_id": TEST_SENSOR.entity_id},
            "{{ states('sensor.test_state') }}",
            "name",
            "{{ states('sensor.test_state') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_duplicate_templates(hass: HomeAssistant) -> None:
    """Test template entity where the value and friendly name as the same template."""
    await async_trigger(hass, TEST_STATE_SENSOR, "Abc")
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state.attributes["friendly_name"] == "Abc"
    assert state.state == "Abc"

    await async_trigger(hass, TEST_STATE_SENSOR, "Def")
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state.attributes["friendly_name"] == "Def"
    assert state.state == "Def"


@pytest.mark.parametrize(("count", "domain"), [(1, template.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "condition": [
                        {
                            "condition": "template",
                            "value_template": "{{ trigger.event.data.beer >= 42 }}",
                        }
                    ],
                    "sensor": [
                        {
                            "name": "Enough Name",
                            "unique_id": "enough-id",
                            "state": "You had enough Beer.",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_conditional_entity(hass: HomeAssistant) -> None:
    """Test conditional trigger entity works."""
    state = hass.states.get("sensor.enough_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.enough_name")
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire("test_event", {"beer": 42})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.enough_name")
    assert state.state == "You had enough Beer."


@pytest.mark.parametrize(("count", "domain"), [(1, template.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "condition": [
                        {
                            "condition": "template",
                            "value_template": "{{ trigger.event.data.beer / 0 == 'narf' }}",
                        }
                    ],
                    "sensor": [
                        {
                            "name": "Enough Name",
                            "unique_id": "enough-id",
                            "state": "You had enough Beer.",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_conditional_entity_evaluation_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test trigger entity is not updated when condition evaluation fails."""
    hass.bus.async_fire("test_event", {"beer": 1})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.enough_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    assert "Error evaluating condition in 'template entity'" in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(0, template.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "condition": [
                        {"condition": "template", "value_template": "{{ invalid"}
                    ],
                    "sensor": [
                        {
                            "name": "Will Not Exist Name",
                            "state": "Unimportant",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_conditional_entity_invalid_condition(
    hass: HomeAssistant,
) -> None:
    """Test trigger entity is not created when condition is invalid."""
    state = hass.states.get("sensor.will_not_exist_name")
    assert state is None


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensors": {
                        "hello_name": {
                            "friendly_name": "Hello Name",
                            "value_template": "{{ trigger.event.data.beer }}",
                            "entity_picture_template": "{{ '/local/dogs.png' }}",
                            "icon_template": "{{ 'mdi:pirate' }}",
                            "attribute_templates": {
                                "last": "{{now().strftime('%D %X')}}",
                                "history_1": "{{this.attributes.last|default('Not yet set')}}",
                            },
                        },
                    },
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_entity_runs_once(hass: HomeAssistant) -> None:
    """Test trigger entity handles a trigger once."""
    state = hass.states.get("sensor.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello_name")
    assert state.state == "2"
    assert state.attributes.get("last") == ANY
    assert state.attributes.get("history_1") == "Not yet set"


@pytest.mark.parametrize(("count", "domain"), [(0, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}",
                        "friendly_name_template": "{{ states.sensor.test_state.state }}",
                    }
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_not_allowed_platform_config(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test we throw a helpful warning if a trigger is configured in platform config."""
    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state is None
    assert (
        "Invalid config for 'sensor' from integration 'template': 'trigger' is an invalid option for"
        in caplog_setup_text
    )


@pytest.mark.parametrize(("source_event_value"), [None, "None"])
async def test_numeric_trigger_entity_set_unknown(
    hass: HomeAssistant, source_event_value: str | None
) -> None:
    """Test trigger entity state parsing with numeric sensors."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensor": [
                        {
                            "name": "Source",
                            "state": "{{ trigger.event.data.value }}",
                        },
                    ],
                },
            ],
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event", {"value": 1})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.source")
    assert state is not None
    assert state.state == "1"

    hass.bus.async_fire("test_event", {"value": source_event_value})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.source")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_trigger_attribute_order(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test trigger entity attributes order."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensor": [
                        {
                            "name": "Test Sensor",
                            "availability": "{{ trigger and trigger.event.data.beer == 2 }}",
                            "state": "{{ trigger.event.data.beer }}",
                            "attributes": {
                                "beer": "{{ trigger.event.data.beer }}",
                                "no_beer": "{{ sad - 1 }}",
                                "more_beer": "{{ beer + 1 }}",
                                "all_the_beer": "{{ this.state | int + more_beer }}",
                            },
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    # Sensors are unknown if never triggered
    state = hass.states.get("sensor.test_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor")
    assert state.state == "2"

    assert state.attributes["beer"] == 2
    assert "no_beer" not in state.attributes
    assert (
        "Error rendering attributes.no_beer template for sensor.test_sensor: UndefinedError: 'sad' is undefined"
        in caplog.text
    )
    assert state.attributes["more_beer"] == 3
    assert (
        "Error rendering attributes.all_the_beer template for sensor.test_sensor: ValueError: Template error: int got invalid input 'unknown' when rendering template '{{ this.state | int + more_beer }}' but no default was specified"
        in caplog.text
    )

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor")
    assert state.state == "2"

    assert state.attributes["beer"] == 2
    assert state.attributes["more_beer"] == 3
    assert state.attributes["all_the_beer"] == 5

    assert (
        caplog.text.count(
            "Error rendering attributes.no_beer template for sensor.test_sensor: UndefinedError: 'sad' is undefined"
        )
        == 2
    )


async def test_trigger_entity_device_class_parsing_works(hass: HomeAssistant) -> None:
    """Test trigger entity device class parsing works."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensor": [
                        {
                            "name": "Date entity",
                            "state": "{{ now().date() }}",
                            "device_class": "date",
                        },
                        {
                            "name": "Timestamp entity",
                            "state": "{{ now() }}",
                            "device_class": "timestamp",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    # State of timestamp sensors are always in UTC
    now = dt_util.utcnow()

    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.date_entity")
    assert date_state is not None
    assert date_state.state == now.date().isoformat()

    ts_state = hass.states.get("sensor.timestamp_entity")
    assert ts_state is not None
    assert ts_state.state == now.isoformat(timespec="seconds")


async def test_trigger_entity_device_class_errors_works(hass: HomeAssistant) -> None:
    """Test trigger entity device class errors works."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensor": [
                        {
                            "name": "Date entity",
                            "state": "invalid",
                            "device_class": "date",
                        },
                        {
                            "name": "Timestamp entity",
                            "state": "invalid",
                            "device_class": "timestamp",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    now = dt_util.now()

    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.date_entity")
    assert date_state is not None
    assert date_state.state == STATE_UNKNOWN

    ts_state = hass.states.get("sensor.timestamp_entity")
    assert ts_state is not None
    assert ts_state.state == STATE_UNKNOWN


async def test_entity_last_reset_total_increasing(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test last_reset is disallowed for total_increasing state_class."""
    # State of timestamp sensors are always in UTC
    now = dt_util.utcnow()

    with patch("homeassistant.util.dt.now", return_value=now):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": [
                    {
                        "sensor": [
                            {
                                "name": "TotalIncreasing entity",
                                "state": "{{ 0 }}",
                                "state_class": "total_increasing",
                                "last_reset": "{{ today_at('00:00:00')}}",
                            },
                        ],
                    },
                ],
            },
        )
        await hass.async_block_till_done()

    totalincreasing_state = hass.states.get("sensor.totalincreasing_entity")
    assert totalincreasing_state is None

    assert (
        "last_reset is only valid for template sensors with state_class 'total'"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template", "attribute"),
    [
        (
            1,
            {"state_class": "total"},
            "{{ states('sensor.test_state') | int(0) }}",
            "last_reset",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        (
            "{{ '2023-01-01T00:00:00.000+00:00' | as_datetime }}",
            "2023-01-01T00:00:00+00:00",
        ),
        (
            "2023-01-01T00:00:00",
            datetime(2023, 1, 1, 0, 0, 0).isoformat(),
        ),
        (
            "{{ as_datetime('2023-01-01') }}",
            datetime(2023, 1, 1).isoformat(),
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_last_reset(hass: HomeAssistant, expected: str) -> None:
    """Test last_reset."""
    await async_trigger(hass, "sensor.test_state", "0")

    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes["state_class"] == "total"
    assert state.attributes["last_reset"] == expected


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template", "attribute", "attribute_template"),
    [
        (
            1,
            {"state_class": "total"},
            "{{ states('sensor.test_state') | int(0) }}",
            "last_reset",
            "{{ 'not a datetime' }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_state_sensor")
async def test_invalid_last_reset(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test last_reset works for template sensors."""
    await async_trigger(hass, "sensor.test_state", "0")

    state = hass.states.get(TEST_SENSOR.entity_id)
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes.get("last_reset") is None

    err = "Received invalid sensor last_reset: not a datetime for entity"
    assert err in caplog_setup_text or err in caplog.text


async def test_entity_device_class_errors_works(hass: HomeAssistant) -> None:
    """Test entity device class errors works."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "sensor": [
                        {
                            "name": "Date entity",
                            "state": "invalid",
                            "device_class": "date",
                        },
                        {
                            "name": "Timestamp entity",
                            "state": "invalid",
                            "device_class": "timestamp",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    now = dt_util.now()

    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.date_entity")
    assert date_state is not None
    assert date_state.state == STATE_UNKNOWN

    ts_state = hass.states.get("sensor.timestamp_entity")
    assert ts_state is not None
    assert ts_state.state == STATE_UNKNOWN


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.data.beer }}",
                    "picture": "{{ '/local/dogs.png' }}",
                    "icon": "{{ 'mdi:pirate' }}",
                    "attributes": {
                        "plus_one": "{{ trigger.event.data.beer + 1 }}",
                        "another": "{{ trigger.event.data.uno_mas or 1 }}",
                    },
                },
            },
        },
    ],
)
@pytest.mark.parametrize(
    ("restored_state", "restored_native_value", "initial_state", "initial_attributes"),
    [
        # the native value should be used, not the state
        ("dog", 10, "10", ["entity_picture", "icon", "plus_one"]),
        (STATE_UNAVAILABLE, 10, STATE_UNKNOWN, []),
        (STATE_UNKNOWN, 10, STATE_UNKNOWN, []),
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    count,
    domain,
    config,
    restored_state,
    restored_native_value,
    initial_state,
    initial_attributes,
) -> None:
    """Test restoring trigger template binary sensor."""

    restored_attributes = {
        "entity_picture": "/local/cats.png",
        "icon": "mdi:ship",
        "plus_one": 55,
    }

    fake_state = State(
        "sensor.test",
        restored_state,
        restored_attributes,
    )
    fake_extra_data = {
        "native_value": restored_native_value,
        "native_unit_of_measurement": None,
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

    state = hass.states.get("sensor.test")
    assert state.state == initial_state
    for attr, value in restored_attributes.items():
        if attr in initial_attributes:
            assert state.attributes[attr] == value
        else:
            assert attr not in state.attributes
    assert "another" not in state.attributes

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state.state == "2"
    assert state.attributes["icon"] == "mdi:pirate"
    assert state.attributes["entity_picture"] == "/local/dogs.png"
    assert state.attributes["plus_one"] == 3
    assert state.attributes["another"] == 1


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [
                        {
                            "variables": {
                                "my_variable": "{{ trigger.event.data.beer + 1 }}"
                            },
                        },
                        {"event": "test_event2", "event_data": {"hello": "world"}},
                    ],
                    "sensor": [
                        {
                            "name": "Hello Name",
                            "state": "{{ my_variable + 1 }}",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_action(hass: HomeAssistant) -> None:
    """Test trigger entity with an action works."""
    event = "test_event2"
    context = Context()
    events = async_capture_events(hass, event)

    state = hass.states.get("sensor.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello_name")
    assert state.state == "3"
    assert state.context is context

    assert len(events) == 1
    assert events[0].context.parent_id == context.id


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "variables": {"a": "{{ trigger.event.data.a }}"},
                    "action": [
                        {
                            "variables": {"b": "{{ a + 1 }}"},
                        },
                        {"event": "test_event2", "event_data": {"hello": "world"}},
                    ],
                    "sensor": [
                        {
                            "name": "Hello Name",
                            "state": "{{ a + b + c }}",
                            "variables": {"c": "{{ b + 1 }}"},
                            "attributes": {
                                "a": "{{ a }}",
                                "b": "{{ b }}",
                                "c": "{{ c }}",
                            },
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_action_variables(hass: HomeAssistant) -> None:
    """Test trigger entity with variables in an action works."""
    event = "test_event2"
    context = Context()
    events = async_capture_events(hass, event)

    state = hass.states.get("sensor.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"a": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello_name")
    assert state.state == str(1 + 2 + 3)
    assert state.context is context
    assert state.attributes["a"] == 1
    assert state.attributes["b"] == 2
    assert state.attributes["c"] == 3

    assert len(events) == 1
    assert events[0].context.parent_id == context.id


@pytest.mark.parametrize(("count", "domain"), [(1, template.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "condition": [
                        {
                            "condition": "template",
                            "value_template": "{{ trigger.event.data.beer >= 42 }}",
                        }
                    ],
                    "action": [
                        {"event": "test_event_by_action"},
                    ],
                    "sensor": [
                        {
                            "name": "Not That Important",
                            "state": "Really not.",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_conditional_action(hass: HomeAssistant) -> None:
    """Test conditional trigger entity with an action works."""

    event = "test_event_by_action"
    events = async_capture_events(hass, event)

    hass.bus.async_fire("test_event", {"beer": 1})
    await hass.async_block_till_done()

    assert len(events) == 0

    hass.bus.async_fire("test_event", {"beer": 42})
    await hass.async_block_till_done()

    assert len(events) == 1


@pytest.mark.parametrize("trigger_field", ["trigger", "triggers"])
@pytest.mark.parametrize("condition_field", ["condition", "conditions"])
@pytest.mark.parametrize("action_field", ["action", "actions"])
async def test_legacy_and_new_config_schema(
    hass: HomeAssistant, trigger_field: str, condition_field: str, action_field: str
) -> None:
    """Tests that both old and new config schema (singular -> plural) work."""

    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    f"{trigger_field}": {
                        "platform": "event",
                        "event_type": "beer_event",
                    },
                    f"{condition_field}": [
                        {
                            "condition": "template",
                            "value_template": "{{ trigger.event.data.beer >= 42 }}",
                        }
                    ],
                    f"{action_field}": [
                        {"event": "test_event_by_action"},
                    ],
                    "sensor": [
                        {
                            "name": "Unimportant",
                            "state": "Uninteresting",
                        }
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    event = "test_event_by_action"
    events = async_capture_events(hass, event)

    hass.bus.async_fire("beer_event", {"beer": 1})
    await hass.async_block_till_done()

    assert len(events) == 0

    hass.bus.async_fire("beer_event", {"beer": 42})
    await hass.async_block_till_done()

    assert len(events) == 1


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
            "state": "{{10}}",
            "template_type": "sensor",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("sensor.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        sensor.DOMAIN,
        {"name": "My template", "state": "{{ 0.0 }}"},
    )

    assert state["state"] == "0.0"


@pytest.mark.parametrize(
    ("count", "config", "state_template"),
    [
        (
            1,
            {
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "°C",
            },
            "{{ states('sensor.test_state') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_state_sensor")
async def test_numeric_sensor_recovers_from_exception(hass: HomeAssistant) -> None:
    """Test template."""
    assert hass.states.get(TEST_SENSOR.entity_id).state == STATE_UNKNOWN

    for set_state, expected_state in (
        ("0.0", "0.0"),
        ("unavailable", STATE_UNKNOWN),
        ("1.0", "1.0"),
        ("unknown", STATE_UNKNOWN),
        ("2.0", "2.0"),
        ("kjfdah", STATE_UNKNOWN),
        ("3.0", "3.0"),
        ("3.x", STATE_UNKNOWN),
        ("4.0", "4.0"),
    ):
        await async_trigger(hass, TEST_STATE_SENSOR, set_state)
        assert hass.states.get(TEST_SENSOR.entity_id).state == expected_state
