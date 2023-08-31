"""The test for the Template sensor platform."""
from asyncio import Event
from datetime import timedelta
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.bootstrap import async_from_config_dict
from homeassistant.components import sensor, template
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.template import Template
from homeassistant.setup import ATTR_COMPONENT, async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

TEST_NAME = "sensor.test_template_sensor"


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


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "It {{ states.sensor.test_state.state }}."
                    }
                },
            },
        },
    ],
)
async def test_template_legacy(hass: HomeAssistant, start_ha) -> None:
    """Test template."""
    assert hass.states.get(TEST_NAME).state == "It ."

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    assert hass.states.get(TEST_NAME).state == "It Works."


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}",
                        "icon_template": "{% if states.sensor.test_state.state == "
                        "'Works' %}"
                        "mdi:check"
                        "{% endif %}",
                    }
                },
            },
        },
    ],
)
async def test_icon_template(hass: HomeAssistant, start_ha) -> None:
    """Test icon template."""
    assert hass.states.get(TEST_NAME).attributes.get("icon") == ""

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    assert hass.states.get(TEST_NAME).attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}",
                        "entity_picture_template": "{% if states.sensor.test_state.state == "
                        "'Works' %}"
                        "/local/sensor.png"
                        "{% endif %}",
                    }
                },
            },
        },
    ],
)
async def test_entity_picture_template(hass: HomeAssistant, start_ha) -> None:
    """Test entity_picture template."""
    assert hass.states.get(TEST_NAME).attributes.get("entity_picture") == ""

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    assert (
        hass.states.get(TEST_NAME).attributes["entity_picture"] == "/local/sensor.png"
    )


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    ("attribute", "config", "expected"),
    [
        (
            "friendly_name",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "{{ states.sensor.test_state.state }}",
                            "friendly_name_template": "It {{ states.sensor.test_state.state }}.",
                        }
                    },
                },
            },
            ("It .", "It Works."),
        ),
        (
            "friendly_name",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "{{ states.sensor.test_state.state }}",
                            "friendly_name_template": "{{ 'It ' + states.sensor.test_state.state + '.'}}",
                        }
                    },
                },
            },
            (None, "It Works."),
        ),
        (
            "friendly_name",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "{{ states.fourohfour.state }}",
                            "friendly_name_template": "It {{ states.sensor.test_state.state }}.",
                        }
                    },
                },
            },
            ("It .", "It Works."),
        ),
        (
            "test_attribute",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "{{ states.sensor.test_state.state }}",
                            "attribute_templates": {
                                "test_attribute": "It {{ states.sensor.test_state.state }}."
                            },
                        }
                    },
                },
            },
            ("It .", "It Works."),
        ),
    ],
)
async def test_friendly_name_template(
    hass: HomeAssistant, attribute, expected, start_ha
) -> None:
    """Test friendly_name template with an unknown value_template."""
    assert hass.states.get(TEST_NAME).attributes.get(attribute) == expected[0]

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    assert hass.states.get(TEST_NAME).attributes[attribute] == expected[1]


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
async def test_template_syntax_error(hass: HomeAssistant, start_ha) -> None:
    """Test setup with invalid device_class."""
    assert hass.states.async_all("sensor") == []


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "It {{ states.sensor.test_state"
                        ".attributes.missing }}."
                    }
                },
            },
        },
    ],
)
async def test_template_attribute_missing(hass: HomeAssistant, start_ha) -> None:
    """Test missing attribute template."""
    assert hass.states.get(TEST_NAME).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test1": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "unit_of_measurement": "°C",
                        "device_class": "temperature",
                    },
                    "test2": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            },
        },
    ],
)
async def test_setup_valid_device_class(hass: HomeAssistant, start_ha) -> None:
    """Test setup with valid device_class."""
    hass.states.async_set("sensor.test_sensor", "75")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test1").attributes["device_class"] == "temperature"
    assert "device_class" not in hass.states.get("sensor.test2").attributes


@pytest.mark.parametrize("load_registries", [False])
async def test_creating_sensor_loads_group(hass: HomeAssistant) -> None:
    """Test setting up template sensor loads group component first."""
    order = []
    after_dep_event = Event()

    async def async_setup_group(hass, config):
        # Make sure group takes longer to load, so that it won't
        # be loaded first by chance
        await after_dep_event.wait()

        order.append("group")
        return True

    async def async_setup_template(
        hass, config, async_add_entities, discovery_info=None
    ):
        order.append("sensor.template")
        return True

    async def set_after_dep_event(event):
        if event.data[ATTR_COMPONENT] == "sensor":
            after_dep_event.set()

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, set_after_dep_event)

    with patch(
        "homeassistant.components.group.async_setup",
        new=async_setup_group,
    ), patch(
        "homeassistant.components.template.sensor.async_setup_platform",
        new=async_setup_template,
    ):
        await async_from_config_dict(
            {"sensor": {"platform": "template", "sensors": {}}, "group": {}}, hass
        )
        await hass.async_block_till_done()

    assert order == ["group", "sensor.template"]


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "availability_template": "{{ is_state('sensor.availability_sensor', 'on') }}",
                    }
                },
            },
        },
    ],
)
async def test_available_template_with_entities(hass: HomeAssistant, start_ha) -> None:
    """Test availability tempalates with values from other entities."""
    hass.states.async_set("sensor.availability_sensor", STATE_OFF)

    # When template returns true..
    hass.states.async_set("sensor.availability_sensor", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get(TEST_NAME).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("sensor.availability_sensor", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get(TEST_NAME).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "invalid_template": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "attribute_templates": {
                            "test_attribute": "{{ states.sensor.unknown.attributes.picture }}"
                        },
                    }
                },
            },
        },
    ],
)
async def test_invalid_attribute_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, start_ha, caplog_setup_text
) -> None:
    """Test that errors are logged if rendering template fails."""
    hass.states.async_set("sensor.test_sensor", "startup")
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    await async_update_entity(hass, "sensor.invalid_template")
    assert "TemplateError" in caplog_setup_text
    assert "test_attribute" in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "my_sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}",
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            },
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("sensor.my_sensor").state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


async def test_no_template_match_all(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we allow static templates."""
    hass.states.async_set("sensor.test_sensor", "startup")

    hass.state = CoreState.not_running

    await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "invalid_state": {"value_template": "{{ 1 + 1 }}"},
                    "invalid_icon": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "icon_template": "{{ 1 + 1 }}",
                    },
                    "invalid_entity_picture": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "entity_picture_template": "{{ 1 + 1 }}",
                    },
                    "invalid_friendly_name": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "friendly_name_template": "{{ 1 + 1 }}",
                    },
                    "invalid_attribute": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "attribute_templates": {"test_attribute": "{{ 1 + 1 }}"},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "unknown"
    assert hass.states.get("sensor.invalid_icon").state == "unknown"
    assert hass.states.get("sensor.invalid_entity_picture").state == "unknown"
    assert hass.states.get("sensor.invalid_friendly_name").state == "unknown"

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 6

    assert hass.states.get("sensor.invalid_state").state == "unknown"
    assert hass.states.get("sensor.invalid_icon").state == "unknown"
    assert hass.states.get("sensor.invalid_entity_picture").state == "unknown"
    assert hass.states.get("sensor.invalid_friendly_name").state == "unknown"
    assert hass.states.get("sensor.invalid_attribute").state == "unknown"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "2"
    assert hass.states.get("sensor.invalid_icon").state == "startup"
    assert hass.states.get("sensor.invalid_entity_picture").state == "startup"
    assert hass.states.get("sensor.invalid_friendly_name").state == "startup"
    assert hass.states.get("sensor.invalid_attribute").state == "startup"

    hass.states.async_set("sensor.test_sensor", "hello")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "2"
    # Will now process because we have at least one valid template
    assert hass.states.get("sensor.invalid_icon").state == "hello"
    assert hass.states.get("sensor.invalid_entity_picture").state == "hello"
    assert hass.states.get("sensor.invalid_friendly_name").state == "hello"
    assert hass.states.get("sensor.invalid_attribute").state == "hello"

    await async_update_entity(hass, "sensor.invalid_state")
    await async_update_entity(hass, "sensor.invalid_icon")
    await async_update_entity(hass, "sensor.invalid_entity_picture")
    await async_update_entity(hass, "sensor.invalid_friendly_name")
    await async_update_entity(hass, "sensor.invalid_attribute")

    assert hass.states.get("sensor.invalid_state").state == "2"
    assert hass.states.get("sensor.invalid_icon").state == "hello"
    assert hass.states.get("sensor.invalid_entity_picture").state == "hello"
    assert hass.states.get("sensor.invalid_friendly_name").state == "hello"
    assert hass.states.get("sensor.invalid_attribute").state == "hello"


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "unique_id": "group-id",
                "sensor": {"name": "top-level", "unique_id": "sensor-id", "state": "5"},
            },
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_sensor_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            },
        },
    ],
)
async def test_unique_id(
    hass: HomeAssistant, start_ha, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option only creates one sensor per id."""
    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id(
        "sensor", "template", "group-id-sensor-id"
    )
    assert entity_registry.async_get_entity_id(
        "sensor", "template", "not-so-unique-anymore"
    )


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "solar_angle": {
                        "friendly_name": "Sun angle",
                        "unit_of_measurement": "degrees",
                        "value_template": "{{ state_attr('sun.sun', 'elevation') }}",
                    },
                    "sunrise": {
                        "value_template": "{{ state_attr('sun.sun', 'next_rising') }}"
                    },
                },
            }
        },
    ],
)
async def test_sun_renders_once_per_sensor(hass: HomeAssistant, start_ha) -> None:
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

    assert hass.states.get("sensor.solar_angle").state == "75"
    assert hass.states.get("sensor.sunrise").state == "75"

    assert len(async_render_calls) == 2
    assert set(async_render_calls) == {
        "{{ state_attr('sun.sun', 'elevation') }}",
        "{{ state_attr('sun.sun', 'next_rising') }}",
    }


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "sensor": {
                    "name": "test_template_sensor",
                    "state": "{{ this.attributes.test }}: {{ this.entity_id }}",
                    "attributes": {"test": "It {{ states.sensor.test_state.state }}"},
                },
            },
        },
        {
            "template": {
                "trigger": {
                    "platform": "state",
                    "entity_id": [
                        "sensor.test_state",
                        "sensor.test_template_sensor",
                    ],
                },
                "sensor": {
                    "name": "test_template_sensor",
                    "state": "{{ this.attributes.test }}: {{ this.entity_id }}",
                    "attributes": {"test": "It {{ states.sensor.test_state.state }}"},
                },
            },
        },
    ],
)
async def test_this_variable(hass: HomeAssistant, start_ha) -> None:
    """Test template."""
    assert hass.states.get(TEST_NAME).state == "It: " + TEST_NAME

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert hass.states.get(TEST_NAME).state == "It Works: " + TEST_NAME


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

    hass.state = CoreState.not_running

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
    assert hass.state == CoreState.running
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


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "value_template": "{{ ((states.sensor.test.state or 0) | int) + 1 }}",
                    },
                },
            }
        },
    ],
)
async def test_self_referencing_sensor_loop(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test a self referencing sensor does not loop forever."""
    assert len(hass.states.async_all()) == 1
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Template loop detected" in caplog_setup_text
    assert int(hass.states.get("sensor.test").state) == 2
    await hass.async_block_till_done()
    assert int(hass.states.get("sensor.test").state) == 2


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "value_template": "{{ ((states.sensor.test.state or 0) | int) + 1 }}",
                        "icon_template": "{% if ((states.sensor.test.state or 0) | int) >= 1 %}mdi:greater{% else %}mdi:less{% endif %}",
                    },
                },
            }
        },
    ],
)
async def test_self_referencing_sensor_with_icon_loop(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test a self referencing sensor loops forever with a valid self referencing icon."""
    assert len(hass.states.async_all()) == 1
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Template loop detected" in caplog_setup_text

    state = hass.states.get("sensor.test")
    assert int(state.state) == 3
    assert state.attributes[ATTR_ICON] == "mdi:greater"
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert int(state.state) == 3


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "value_template": "{{ ((states.sensor.test.state or 0) | int) + 1 }}",
                        "icon_template": "{% if ((states.sensor.test.state or 0) | int) > 3 %}mdi:greater{% else %}mdi:less{% endif %}",
                        "entity_picture_template": "{% if ((states.sensor.test.state or 0) | int) >= 1 %}bigpic{% else %}smallpic{% endif %}",
                    },
                },
            }
        },
    ],
)
async def test_self_referencing_sensor_with_icon_and_picture_entity_loop(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test a self referencing sensor loop forevers with a valid self referencing icon."""
    assert len(hass.states.async_all()) == 1
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Template loop detected" in caplog_setup_text

    state = hass.states.get("sensor.test")
    assert int(state.state) == 4
    assert state.attributes[ATTR_ICON] == "mdi:less"
    assert state.attributes[ATTR_ENTITY_PICTURE] == "bigpic"

    await hass.async_block_till_done()
    assert int(state.state) == 4


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "value_template": "{{ 1 }}",
                        "entity_picture_template": "{{ ((states.sensor.test.attributes['entity_picture'] or 0) | int) + 1 }}",
                    },
                },
            }
        },
    ],
)
async def test_self_referencing_entity_picture_loop(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test a self referencing sensor does not loop forever with a looping self referencing entity picture."""
    assert len(hass.states.async_all()) == 1
    next_time = dt_util.utcnow() + timedelta(seconds=1.2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert "Template loop detected" in caplog_setup_text

    state = hass.states.get("sensor.test")
    assert int(state.state) == 1
    assert state.attributes[ATTR_ENTITY_PICTURE] == 2

    await hass.async_block_till_done()
    assert int(state.state) == 1


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
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "heartworm_risk": {
                        "value_template": value_template_str,
                        "icon_template": icon_template_str,
                    },
                },
            }
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


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
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
async def test_duplicate_templates(hass: HomeAssistant, start_ha) -> None:
    """Test template entity where the value and friendly name as the same template."""
    hass.states.async_set("sensor.test_state", "Abc")
    await hass.async_block_till_done()
    state = hass.states.get(TEST_NAME)
    assert state.attributes["friendly_name"] == "Abc"
    assert state.state == "Abc"

    hass.states.async_set("sensor.test_state", "Def")
    await hass.async_block_till_done()
    state = hass.states.get(TEST_NAME)
    assert state.attributes["friendly_name"] == "Def"
    assert state.state == "Def"


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
                    "sensors": {
                        "hello": {
                            "friendly_name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "device_class": "battery",
                            "unit_of_measurement": "%",
                            "value_template": "{{ trigger.event.data.beer }}",
                            "entity_picture_template": "{{ '/local/dogs.png' }}",
                            "icon_template": "{{ 'mdi:pirate' }}",
                            "attribute_templates": {
                                "plus_one": "{{ trigger.event.data.beer + 1 }}"
                            },
                        },
                    },
                    "sensor": [
                        {
                            "name": "via list",
                            "unique_id": "via_list-id",
                            "device_class": "battery",
                            "unit_of_measurement": "%",
                            "availability": "{{ True }}",
                            "state": "{{ trigger.event.data.beer + 1 }}",
                            "picture": "{{ '/local/dogs.png' }}",
                            "icon": "{{ 'mdi:pirate' }}",
                            "attributes": {
                                "plus_one": "{{ trigger.event.data.beer + 1 }}"
                            },
                            "state_class": "measurement",
                        }
                    ],
                },
                {
                    "trigger": [],
                    "sensors": {
                        "bare_minimum": {
                            "value_template": "{{ trigger.event.data.beer }}"
                        },
                    },
                },
            ],
        },
    ],
)
async def test_trigger_entity(
    hass: HomeAssistant, start_ha, entity_registry: er.EntityRegistry
) -> None:
    """Test trigger entity works."""
    state = hass.states.get("sensor.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("sensor.bare_minimum")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello_name")
    assert state.state == "2"
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.attributes.get("plus_one") == 3
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.context is context

    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.entities["sensor.hello_name"].unique_id
        == "listening-test-event-hello_name-id"
    )
    assert (
        entity_registry.entities["sensor.via_list"].unique_id
        == "listening-test-event-via_list-id"
    )

    state = hass.states.get("sensor.via_list")
    assert state.state == "3"
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.attributes.get("plus_one") == 3
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("state_class") == "measurement"
    assert state.context is context


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensors": {
                    "hello": {
                        "unique_id": "no-base-id",
                        "friendly_name": "Hello",
                        "value_template": "{{ non_existing + 1 }}",
                    }
                },
            },
        },
    ],
)
async def test_trigger_entity_render_error(
    hass: HomeAssistant, start_ha, entity_registry: er.EntityRegistry
) -> None:
    """Test trigger entity handles render error."""
    state = hass.states.get("sensor.hello")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello")
    assert state.state == STATE_UNAVAILABLE

    assert len(entity_registry.entities) == 1
    assert entity_registry.entities["sensor.hello"].unique_id == "no-base-id"


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
async def test_trigger_not_allowed_platform_config(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test we throw a helpful warning if a trigger is configured in platform config."""
    state = hass.states.get(TEST_NAME)
    assert state is None
    assert (
        "You can only add triggers to template entities if they are defined under `template:`."
        in caplog_setup_text
    )


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "sensor": {
                    "name": "top-level",
                    "device_class": "battery",
                    "state_class": "measurement",
                    "state": "5",
                    "unit_of_measurement": "%",
                },
            },
        },
    ],
)
async def test_config_top_level(hass: HomeAssistant, start_ha) -> None:
    """Test unique_id option only creates one sensor per id."""
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("sensor.top_level")
    assert state is not None
    assert state.state == "5"
    assert state.attributes["device_class"] == "battery"
    assert state.attributes["state_class"] == "measurement"


async def test_trigger_entity_available(hass: HomeAssistant) -> None:
    """Test trigger entity availability works."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "sensor": [
                        {
                            "name": "Maybe Available",
                            "availability": "{{ trigger and trigger.event.data.beer == 2 }}",
                            "state": "{{ trigger.event.data.beer }}",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()

    # Sensors are unknown if never triggered
    state = hass.states.get("sensor.maybe_available")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire("test_event", {"beer": 2})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.maybe_available")
    assert state.state == "2"

    hass.bus.async_fire("test_event", {"beer": 1})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.maybe_available")
    assert state.state == "unavailable"


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


async def test_entity_device_class_parsing_works(hass: HomeAssistant) -> None:
    """Test entity device class parsing works."""
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

    date_state = hass.states.get("sensor.date_entity")
    assert date_state is not None
    assert date_state.state == now.date().isoformat()

    ts_state = hass.states.get("sensor.timestamp_entity")
    assert ts_state is not None
    assert ts_state.state == now.isoformat(timespec="seconds")


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
    for attr in restored_attributes:
        if attr in initial_attributes:
            assert state.attributes[attr] == restored_attributes[attr]
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
