"""The tests for template helpers."""

import pytest

from homeassistant.components.template.alarm_control_panel import (
    LEGACY_FIELDS as ALARM_CONTROL_PANEL_LEGACY_FIELDS,
)
from homeassistant.components.template.binary_sensor import (
    LEGACY_FIELDS as BINARY_SENSOR_LEGACY_FIELDS,
)
from homeassistant.components.template.button import StateButtonEntity
from homeassistant.components.template.cover import LEGACY_FIELDS as COVER_LEGACY_FIELDS
from homeassistant.components.template.fan import LEGACY_FIELDS as FAN_LEGACY_FIELDS
from homeassistant.components.template.helpers import (
    async_setup_template_platform,
    create_legacy_template_issue,
    format_migration_config,
    rewrite_legacy_to_modern_config,
    rewrite_legacy_to_modern_configs,
)
from homeassistant.components.template.light import LEGACY_FIELDS as LIGHT_LEGACY_FIELDS
from homeassistant.components.template.lock import LEGACY_FIELDS as LOCK_LEGACY_FIELDS
from homeassistant.components.template.sensor import (
    LEGACY_FIELDS as SENSOR_LEGACY_FIELDS,
)
from homeassistant.components.template.switch import (
    LEGACY_FIELDS as SWITCH_LEGACY_FIELDS,
)
from homeassistant.components.template.vacuum import (
    LEGACY_FIELDS as VACUUM_LEGACY_FIELDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    ("legacy_fields", "old_attr", "new_attr", "attr_template"),
    [
        (
            LOCK_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            LOCK_LEGACY_FIELDS,
            "code_format_template",
            "code_format",
            "{{ 'some format' }}",
        ),
    ],
)
async def test_legacy_to_modern_config(
    hass: HomeAssistant,
    legacy_fields,
    old_attr: str,
    new_attr: str,
    attr_template: str,
) -> None:
    """Test the conversion of single legacy template to modern template."""
    config = {
        "friendly_name": "foo bar",
        "unique_id": "foo-bar-entity",
        "icon_template": "{{ 'mdi.abc' }}",
        "entity_picture_template": "{{ 'mypicture.jpg' }}",
        "availability_template": "{{ 1 == 1 }}",
        old_attr: attr_template,
    }
    altered_configs = rewrite_legacy_to_modern_config(hass, config, legacy_fields)

    assert {
        "availability": Template("{{ 1 == 1 }}", hass),
        "icon": Template("{{ 'mdi.abc' }}", hass),
        "name": Template("foo bar", hass),
        "picture": Template("{{ 'mypicture.jpg' }}", hass),
        "unique_id": "foo-bar-entity",
        new_attr: Template(attr_template, hass),
    } == altered_configs


@pytest.mark.parametrize(
    ("domain", "legacy_fields", "old_attr", "new_attr", "attr_template"),
    [
        (
            "alarm_control_panel",
            ALARM_CONTROL_PANEL_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "binary_sensor",
            BINARY_SENSOR_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "cover",
            COVER_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "cover",
            COVER_LEGACY_FIELDS,
            "position_template",
            "position",
            "{{ 100 }}",
        ),
        (
            "cover",
            COVER_LEGACY_FIELDS,
            "tilt_template",
            "tilt",
            "{{ 100 }}",
        ),
        (
            "fan",
            FAN_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "fan",
            FAN_LEGACY_FIELDS,
            "direction_template",
            "direction",
            "{{ 1 == 1 }}",
        ),
        (
            "fan",
            FAN_LEGACY_FIELDS,
            "oscillating_template",
            "oscillating",
            "{{ True }}",
        ),
        (
            "fan",
            FAN_LEGACY_FIELDS,
            "percentage_template",
            "percentage",
            "{{ 100 }}",
        ),
        (
            "fan",
            FAN_LEGACY_FIELDS,
            "preset_mode_template",
            "preset_mode",
            "{{ 'foo' }}",
        ),
        (
            "fan",
            LIGHT_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "rgb_template",
            "rgb",
            "{{ (255,255,255) }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "rgbw_template",
            "rgbw",
            "{{ (255,255,255,255) }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "rgbww_template",
            "rgbww",
            "{{ (255,255,255,255,255) }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "effect_list_template",
            "effect_list",
            "{{ ['a', 'b'] }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "effect_template",
            "effect",
            "{{ 'a' }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "level_template",
            "level",
            "{{ 255 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "max_mireds_template",
            "max_mireds",
            "{{ 255 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "min_mireds_template",
            "min_mireds",
            "{{ 255 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "supports_transition_template",
            "supports_transition",
            "{{ True }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "temperature_template",
            "temperature",
            "{{ 255 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "white_value_template",
            "white_value",
            "{{ 255 }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "hs_template",
            "hs",
            "{{ (255, 255) }}",
        ),
        (
            "light",
            LIGHT_LEGACY_FIELDS,
            "color_template",
            "hs",
            "{{ (255, 255) }}",
        ),
        (
            "sensor",
            SENSOR_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "sensor",
            SWITCH_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "vacuum",
            VACUUM_LEGACY_FIELDS,
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "vacuum",
            VACUUM_LEGACY_FIELDS,
            "battery_level_template",
            "battery_level",
            "{{ 100 }}",
        ),
        (
            "vacuum",
            VACUUM_LEGACY_FIELDS,
            "fan_speed_template",
            "fan_speed",
            "{{ 7 }}",
        ),
    ],
)
async def test_legacy_to_modern_configs(
    hass: HomeAssistant,
    domain: str,
    legacy_fields,
    old_attr: str,
    new_attr: str,
    attr_template: str,
) -> None:
    """Test the conversion of legacy template to modern template."""
    config = {
        "foo": {
            "friendly_name": "foo bar",
            "unique_id": "foo-bar-entity",
            "icon_template": "{{ 'mdi.abc' }}",
            "entity_picture_template": "{{ 'mypicture.jpg' }}",
            "availability_template": "{{ 1 == 1 }}",
            old_attr: attr_template,
        }
    }
    altered_configs = rewrite_legacy_to_modern_configs(
        hass, domain, config, legacy_fields
    )

    assert len(altered_configs) == 1

    assert [
        {
            "availability": Template("{{ 1 == 1 }}", hass),
            "icon": Template("{{ 'mdi.abc' }}", hass),
            "name": Template("foo bar", hass),
            "default_entity_id": f"{domain}.foo",
            "picture": Template("{{ 'mypicture.jpg' }}", hass),
            "unique_id": "foo-bar-entity",
            new_attr: Template(attr_template, hass),
        }
    ] == altered_configs


@pytest.mark.parametrize(
    ("domain", "legacy_fields"),
    [
        ("binary_sensor", BINARY_SENSOR_LEGACY_FIELDS),
        ("sensor", SENSOR_LEGACY_FIELDS),
    ],
)
async def test_friendly_name_template_legacy_to_modern_configs(
    hass: HomeAssistant,
    domain: str,
    legacy_fields,
) -> None:
    """Test the conversion of friendly_name_tempalte in legacy template to modern template."""
    config = {
        "foo": {
            "unique_id": "foo-bar-entity",
            "icon_template": "{{ 'mdi.abc' }}",
            "entity_picture_template": "{{ 'mypicture.jpg' }}",
            "availability_template": "{{ 1 == 1 }}",
            "friendly_name_template": "{{ 'foo bar' }}",
        }
    }
    altered_configs = rewrite_legacy_to_modern_configs(
        hass, domain, config, legacy_fields
    )

    assert len(altered_configs) == 1

    assert [
        {
            "availability": Template("{{ 1 == 1 }}", hass),
            "icon": Template("{{ 'mdi.abc' }}", hass),
            "default_entity_id": f"{domain}.foo",
            "picture": Template("{{ 'mypicture.jpg' }}", hass),
            "unique_id": "foo-bar-entity",
            "name": Template("{{ 'foo bar' }}", hass),
        }
    ] == altered_configs


async def test_platform_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_template_platform raises PlatformNotReady when trigger object is None."""
    with pytest.raises(PlatformNotReady):
        await async_setup_template_platform(
            hass,
            "button",
            {},
            StateButtonEntity,
            None,
            None,
            {"coordinator": None, "entities": []},
        )


@pytest.mark.parametrize(
    ("domain", "config", "breadcrumb"),
    [
        (
            "template",
            {
                "template": [
                    {
                        "sensors": {
                            "undocumented_configuration": {
                                "value_template": "{{ 'armed_away' }}",
                            }
                        }
                    },
                ]
            },
            "undocumented_configuration",
        ),
        (
            "template",
            {
                "template": [
                    {
                        "binary_sensors": {
                            "undocumented_configuration": {
                                "value_template": "{{ 'armed_away' }}",
                            }
                        }
                    },
                ]
            },
            "undocumented_configuration",
        ),
        (
            "alarm_control_panel",
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "safe_alarm_panel": {
                            "value_template": "{{ 'armed_away' }}",
                        }
                    },
                },
            },
            "safe_alarm_panel",
        ),
        (
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "template",
                    "sensors": {
                        "sun_up": {
                            "value_template": "{{ state_attr('sun.sun', 'elevation') > 0 }}",
                        }
                    },
                },
            },
            "sun_up",
        ),
        (
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "garage_door": {
                            "value_template": "{{ states('sensor.garage_door')|float > 0 }}",
                            "open_cover": {"action": "script.toggle"},
                            "close_cover": {"action": "script.toggle"},
                        }
                    },
                },
            },
            "garage_door",
        ),
        (
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "bedroom_fan": {
                            "value_template": "{{ states('input_boolean.state') }}",
                            "turn_on": {"action": "script.toggle"},
                            "turn_off": {"action": "script.toggle"},
                        }
                    },
                },
            },
            "bedroom_fan",
        ),
        (
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "theater_lights": {
                            "value_template": "{{ states('input_boolean.state') }}",
                            "turn_on": {"action": "script.toggle"},
                            "turn_off": {"action": "script.toggle"},
                        }
                    },
                },
            },
            "theater_lights",
        ),
        (
            "lock",
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ states('input_boolean.state') }}",
                    "lock": {"action": "script.toggle"},
                    "unlock": {"action": "script.toggle"},
                },
            },
            "Template Entity",
        ),
        (
            "sensor",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "It {{ states.sensor.test_state.state }}.",
                            "attribute_templates": {"something": "{{ 'bar' }}"},
                        }
                    },
                },
            },
            "test_template_sensor",
        ),
        (
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "skylight": {
                            "value_template": "{{ is_state('sensor.skylight', 'on') }}",
                            "turn_on": {"action": "script.toggle"},
                            "turn_off": {"action": "script.toggle"},
                        }
                    },
                },
            },
            "skylight",
        ),
        (
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "living_room_vacuum": {
                            "start": {"action": "script.start"},
                            "attribute_templates": {"something": "{{ 'bar' }}"},
                        }
                    },
                },
            },
            "living_room_vacuum",
        ),
        (
            "weather",
            {
                "weather": {
                    "platform": "template",
                    "name": "My Weather Station",
                    "unique_id": "Foobar",
                    "condition_template": "{{ 'rainy' }}",
                    "temperature_template": "{{ 20 }}",
                    "humidity_template": "{{ 50 }}",
                },
            },
            "unique_id: Foobar",
        ),
        (
            "weather",
            {
                "weather": {
                    "platform": "template",
                    "name": "My Weather Station",
                    "condition_template": "{{ 'rainy' }}",
                    "temperature_template": "{{ 20 }}",
                    "humidity_template": "{{ 50 }}",
                },
            },
            "My Weather Station",
        ),
    ],
)
async def test_legacy_deprecation(
    hass: HomeAssistant,
    domain: str,
    config: dict,
    breadcrumb: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test legacy configuration raises issue."""

    await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    issue = next(iter(issue_registry.issues.values()))

    assert issue.domain == "template"
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["breadcrumb"] == breadcrumb
    assert "platform: template" not in issue.translation_placeholders["config"]


@pytest.mark.parametrize(
    ("domain", "config", "strings_to_check"),
    [
        (
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "garage_light_template": {
                            "friendly_name": "Garage Light Template",
                            "min_mireds_template": 153,
                            "max_mireds_template": 500,
                            "turn_on": [],
                            "turn_off": [],
                            "set_temperature": [],
                            "set_hs": [],
                            "set_level": [],
                        }
                    },
                },
            },
            [
                "turn_on: []",
                "turn_off: []",
                "set_temperature: []",
                "set_hs: []",
                "set_level: []",
            ],
        ),
        (
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "my_switch": {
                            "friendly_name": "Switch Template",
                            "turn_on": [],
                            "turn_off": [],
                        }
                    },
                },
            },
            [
                "turn_on: []",
                "turn_off: []",
            ],
        ),
        (
            "light",
            {
                "light": [
                    {
                        "platform": "template",
                        "lights": {
                            "atrium_lichterkette": {
                                "unique_id": "atrium_lichterkette",
                                "friendly_name": "Atrium Lichterkette",
                                "value_template": "{{ states('input_boolean.atrium_lichterkette_power') }}",
                                "level_template": "{% if is_state('input_boolean.atrium_lichterkette_power', 'off') %}\n  0\n{% else %}\n  {{ states('input_number.atrium_lichterkette_brightness') | int * (255 / state_attr('input_number.atrium_lichterkette_brightness', 'max') | int) }}\n{% endif %}",
                                "effect_list_template": "{{ state_attr('input_select.atrium_lichterkette_mode', 'options') }}",
                                "effect_template": "'{{ states('input_select.atrium_lichterkette_mode')}}'",
                                "turn_on": [
                                    {
                                        "service": "button.press",
                                        "target": {
                                            "entity_id": "button.esphome_web_28a814_lichterkette_on"
                                        },
                                    },
                                    {
                                        "service": "input_boolean.turn_on",
                                        "target": {
                                            "entity_id": "input_boolean.atrium_lichterkette_power"
                                        },
                                    },
                                ],
                                "turn_off": [
                                    {
                                        "service": "button.press",
                                        "target": {
                                            "entity_id": "button.esphome_web_28a814_lichterkette_off"
                                        },
                                    },
                                    {
                                        "service": "input_boolean.turn_off",
                                        "target": {
                                            "entity_id": "input_boolean.atrium_lichterkette_power"
                                        },
                                    },
                                ],
                                "set_level": [
                                    {
                                        "variables": {
                                            "scaled": "{{ (brightness / (255 / state_attr('input_number.atrium_lichterkette_brightness', 'max'))) | round | int }}",
                                            "diff": "{{ scaled | int - states('input_number.atrium_lichterkette_brightness') | int }}",
                                            "direction": "{{ 'dim' if diff | int < 0 else 'bright' }}",
                                        }
                                    },
                                    {
                                        "repeat": {
                                            "count": "{{ diff | int | abs }}",
                                            "sequence": [
                                                {
                                                    "service": "button.press",
                                                    "target": {
                                                        "entity_id": "button.esphome_web_28a814_lichterkette_{{ direction }}"
                                                    },
                                                },
                                                {"delay": {"milliseconds": 500}},
                                            ],
                                        }
                                    },
                                    {
                                        "service": "input_number.set_value",
                                        "data": {
                                            "value": "{{ scaled }}",
                                            "entity_id": "input_number.atrium_lichterkette_brightness",
                                        },
                                    },
                                ],
                                "set_effect": [
                                    {
                                        "service": "button.press",
                                        "target": {
                                            "entity_id": "button.esphome_web_28a814_lichterkette_{{ effect }}"
                                        },
                                    }
                                ],
                            }
                        },
                    }
                ]
            },
            [
                "scaled: ",
                "diff: ",
                "direction: ",
            ],
        ),
        (
            "cover",
            {
                "cover": [
                    {
                        "platform": "template",
                        "covers": {
                            "large_garage_door": {
                                "device_class": "garage",
                                "friendly_name": "Large Garage Door",
                                "value_template": "{% if is_state('binary_sensor.large_garage_door', 'off') %}\n  closed\n{% elif is_state('timer.large_garage_opening_timer', 'active') %}\n  opening\n{% elif is_state('timer.large_garage_closing_timer', 'active') %}            \n  closing\n{% elif is_state('binary_sensor.large_garage_door', 'on') %}\n  open\n{% endif %}\n",
                                "open_cover": [
                                    {
                                        "condition": "state",
                                        "entity_id": "binary_sensor.large_garage_door",
                                        "state": "off",
                                    },
                                    {
                                        "action": "switch.turn_on",
                                        "target": {
                                            "entity_id": "switch.garage_door_relay_1"
                                        },
                                    },
                                    {
                                        "action": "timer.start",
                                        "entity_id": "timer.large_garage_opening_timer",
                                    },
                                ],
                                "close_cover": [
                                    {
                                        "condition": "state",
                                        "entity_id": "binary_sensor.large_garage_door",
                                        "state": "on",
                                    },
                                    {
                                        "action": "switch.turn_on",
                                        "target": {
                                            "entity_id": "switch.garage_door_relay_1"
                                        },
                                    },
                                    {
                                        "action": "timer.start",
                                        "entity_id": "timer.large_garage_closing_timer",
                                    },
                                ],
                                "stop_cover": [
                                    {
                                        "action": "switch.turn_on",
                                        "target": {
                                            "entity_id": "switch.garage_door_relay_1"
                                        },
                                    },
                                    {
                                        "action": "timer.cancel",
                                        "entity_id": "timer.large_garage_opening_timer",
                                    },
                                    {
                                        "action": "timer.cancel",
                                        "entity_id": "timer.large_garage_closing_timer",
                                    },
                                ],
                            }
                        },
                    }
                ]
            },
            ["device_class: garage"],
        ),
        (
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "template",
                    "sensors": {
                        "motion_sensor": {
                            "friendly_name": "Motion Sensor",
                            "device_class": "motion",
                            "value_template": "{{ is_state('sensor.motion_detector', 'on') }}",
                        }
                    },
                },
            },
            ["device_class: motion"],
        ),
        (
            "sensor",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "some_sensor": {
                            "friendly_name": "Sensor",
                            "entity_id": "sensor.some_sensor",
                            "device_class": "timestamp",
                            "value_template": "{{ now().isoformat() }}",
                        }
                    },
                },
            },
            ["device_class: timestamp", "entity_id: sensor.some_sensor"],
        ),
    ],
)
async def test_legacy_deprecation_with_unique_objects(
    hass: HomeAssistant,
    domain: str,
    config: dict,
    strings_to_check: list[str],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test legacy configuration raises issue and unique objects are properly converted to valid configurations."""

    await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    issue = next(iter(issue_registry.issues.values()))

    assert issue.domain == "template"
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders is not None
    for string in strings_to_check:
        assert string in issue.translation_placeholders["config"]


@pytest.mark.parametrize(
    ("domain", "config"),
    [
        (
            "template",
            {"template": [{"sensor": {"name": "test_template_sensor", "state": "OK"}}]},
        ),
        (
            "template",
            {
                "template": [
                    {
                        "triggers": {"trigger": "event", "event_type": "test"},
                        "sensor": {"name": "test_template_sensor", "state": "OK"},
                    }
                ]
            },
        ),
    ],
)
async def test_modern_configuration_does_not_raise_issue(
    hass: HomeAssistant,
    domain: str,
    config: dict,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test modern configuration does not raise issue."""

    await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 0


async def test_yaml_config_recursion_depth(hass: HomeAssistant) -> None:
    """Test recursion depth when formatting ConfigType."""

    with pytest.raises(RecursionError):
        format_migration_config({1: {2: {3: {4: {5: {6: [{7: {8: {9: {10: {}}}}}]}}}}}})


@pytest.mark.parametrize(
    ("domain", "config"),
    [
        (
            "media_player",
            {
                "media_player": {
                    "platform": "template",
                    "name": "My Media Player",
                    "unique_id": "Foobar",
                },
            },
        ),
        (
            "climate",
            {
                "climate": {
                    "platform": "template",
                    "name": "My Climate",
                    "unique_id": "Foobar",
                },
            },
        ),
    ],
)
async def test_custom_integration_deprecation(
    hass: HomeAssistant,
    domain: str,
    config: dict,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that custom integrations do not create deprecations."""

    create_legacy_template_issue(hass, config, domain)
    assert len(issue_registry.issues) == 0
