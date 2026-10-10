"""The tests for template helpers."""

import pytest

from homeassistant.components.template import DOMAIN
from homeassistant.components.template.alarm_control_panel import (
    SCRIPT_FIELDS as ALARM_CONTROL_PANEL_SCRIPT_FIELDS,
)
from homeassistant.components.template.button import (
    SCRIPT_FIELDS as BUTTON_SCRIPT_FIELDS,
    StateButtonEntity,
)
from homeassistant.components.template.cover import SCRIPT_FIELDS as COVER_SCRIPT_FIELDS
from homeassistant.components.template.fan import SCRIPT_FIELDS as FAN_SCRIPT_FIELDS
from homeassistant.components.template.helpers import async_setup_template_platform
from homeassistant.components.template.light import SCRIPT_FIELDS as LIGHT_SCRIPT_FIELDS
from homeassistant.components.template.lock import SCRIPT_FIELDS as LOCK_SCRIPT_FIELDS
from homeassistant.components.template.number import (
    SCRIPT_FIELDS as NUMBER_SCRIPT_FIELDS,
)
from homeassistant.components.template.select import (
    SCRIPT_FIELDS as SELECT_SCRIPT_FIELDS,
)
from homeassistant.components.template.switch import (
    SCRIPT_FIELDS as SWITCH_SCRIPT_FIELDS,
)
from homeassistant.components.template.update import (
    SCRIPT_FIELDS as UPDATE_SCRIPT_FIELDS,
)
from homeassistant.components.template.vacuum import (
    CONF_CLEAN_SEGMENTS as VACUUM_CLEAN_SEGMENTS,
    SCRIPT_FIELDS as VACUUM_SCRIPT_FIELDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    assert_action,
    async_trigger,
    make_mock_device_actions,
    setup_entity,
    setup_mock_devices,
)

from tests.common import MockConfigEntry


async def _setup_and_test_yaml_device_action(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    domain: str,
    script_fields,
    extra_config: ConfigType,
    test_actions: tuple[tuple[str, dict], ...],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls: list,
) -> None:

    platform_setup, device_entry, entity_entry = await setup_mock_devices(
        hass, domain, device_registry, entity_registry
    )

    actions = make_mock_device_actions(
        script_fields, platform_setup, device_entry, entity_entry
    )

    await setup_entity(hass, platform_setup, style, 1, {**actions, **extra_config})
    await async_trigger(hass, "sensor.trigger", "anything")

    for test_action, action_data in test_actions:
        call_count = len(calls)
        await hass.services.async_call(
            domain,
            test_action,
            {"entity_id": platform_setup.entity_id, **action_data},
            blocking=True,
        )
        assert_action(platform_setup, calls, call_count + 1, "fake_action")


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("domain", "script_fields", "extra_config", "test_actions"),
    [
        (
            "alarm_control_panel",
            ALARM_CONTROL_PANEL_SCRIPT_FIELDS,
            {},
            (
                ("alarm_arm_home", {"code": "1234"}),
                ("alarm_arm_away", {"code": "1234"}),
                ("alarm_arm_night", {"code": "1234"}),
                ("alarm_arm_vacation", {"code": "1234"}),
                ("alarm_arm_custom_bypass", {"code": "1234"}),
                ("alarm_disarm", {"code": "1234"}),
                ("alarm_trigger", {"code": "1234"}),
            ),
        ),
        (
            "cover",
            COVER_SCRIPT_FIELDS,
            {},
            (
                ("open_cover", {}),
                ("close_cover", {}),
                ("stop_cover", {}),
                ("set_cover_position", {"position": 25}),
                ("set_cover_tilt_position", {"tilt_position": 25}),
            ),
        ),
        (
            "fan",
            FAN_SCRIPT_FIELDS,
            {
                "preset_modes": ["auto", "low", "medium", "high"],
            },
            (
                ("turn_on", {}),
                ("turn_off", {}),
                ("set_percentage", {"percentage": 25}),
                ("set_preset_mode", {"preset_mode": "auto"}),
                ("oscillate", {"oscillating": True}),
                ("set_direction", {"direction": "forward"}),
            ),
        ),
        (
            "light",
            LIGHT_SCRIPT_FIELDS,
            {"effect_list": "{{ ['foo', 'bar'] }}", "effect": "{{ 'foo' }}"},
            (
                ("turn_on", {"brightness": 1}),
                ("turn_off", {}),
                ("turn_on", {"color_temp_kelvin": 8130}),
                ("turn_on", {"hs_color": (360, 100)}),
                ("turn_on", {"rgb_color": (160, 78, 192)}),
                ("turn_on", {"rgbw_color": (160, 78, 192, 25)}),
                ("turn_on", {"rgbww_color": (160, 78, 192, 25, 55)}),
                ("turn_on", {"effect": "foo"}),
            ),
        ),
        (
            "lock",
            LOCK_SCRIPT_FIELDS,
            {},
            (
                ("lock", {}),
                ("unlock", {}),
                ("open", {}),
            ),
        ),
        (
            "number",
            NUMBER_SCRIPT_FIELDS,
            {"step": "1"},
            (("set_value", {"value": 4}),),
        ),
        (
            "select",
            SELECT_SCRIPT_FIELDS,
            {
                "options": "{{ ['test', 'yes', 'no'] }}",
            },
            (("select_option", {"option": "test"}),),
        ),
        (
            "switch",
            SWITCH_SCRIPT_FIELDS,
            {},
            (
                ("turn_on", {}),
                ("turn_off", {}),
            ),
        ),
        (
            "update",
            UPDATE_SCRIPT_FIELDS,
            {"installed_version": "{{ '2.0.0' }}", "latest_version": "{{ '3.0.0' }}"},
            (("install", {}),),
        ),
        (
            "vacuum",
            [
                service
                for service in VACUUM_SCRIPT_FIELDS
                if service != VACUUM_CLEAN_SEGMENTS
            ],
            {
                "fan_speeds": ["low", "medium", "high"],
            },
            (
                ("start", {}),
                ("pause", {}),
                ("stop", {}),
                ("return_to_base", {}),
                ("clean_spot", {}),
                ("locate", {}),
                ("set_fan_speed", {"fan_speed": "medium"}),
            ),
        ),
    ],
)
async def test_yaml_device_actions(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    domain: str,
    script_fields,
    extra_config: ConfigType,
    test_actions: tuple[tuple[str, dict], ...],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls: list,
) -> None:
    """Test device actions in platforms supporting trigger and modern configs."""
    await _setup_and_test_yaml_device_action(
        hass,
        style,
        domain,
        script_fields,
        extra_config,
        test_actions,
        device_registry,
        entity_registry,
        calls,
    )


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN],
)
@pytest.mark.parametrize(
    ("domain", "script_fields", "extra_config", "test_actions"),
    [
        (
            "button",
            BUTTON_SCRIPT_FIELDS,
            {},
            (("press", {}),),
        ),
    ],
)
async def test_yaml_device_actions_modern_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    domain: str,
    script_fields,
    extra_config: str,
    test_actions: tuple[tuple[str, dict], ...],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls: list,
) -> None:
    """Test device actions in platforms that supports modern configuration only."""
    await _setup_and_test_yaml_device_action(
        hass,
        style,
        domain,
        script_fields,
        extra_config,
        test_actions,
        device_registry,
        entity_registry,
        calls,
    )


@pytest.mark.parametrize(
    ("domain", "script_fields", "extra_config", "test_actions"),
    [
        (
            "alarm_control_panel",
            ALARM_CONTROL_PANEL_SCRIPT_FIELDS,
            {"state": "{{ 'armed' }}"},
            (
                ("alarm_arm_home", {"code": "1234"}),
                ("alarm_arm_away", {"code": "1234"}),
                ("alarm_arm_night", {"code": "1234"}),
                ("alarm_arm_vacation", {"code": "1234"}),
                ("alarm_arm_custom_bypass", {"code": "1234"}),
                ("alarm_disarm", {"code": "1234"}),
                ("alarm_trigger", {"code": "1234"}),
            ),
        ),
        (
            "button",
            BUTTON_SCRIPT_FIELDS,
            {},
            (("press", {}),),
        ),
        (
            "cover",
            COVER_SCRIPT_FIELDS,
            {"state": "{{ 'open' }}"},
            (
                ("open_cover", {}),
                ("close_cover", {}),
                ("stop_cover", {}),
                ("set_cover_position", {"position": 25}),
                ("set_cover_tilt_position", {"tilt_position": 25}),
            ),
        ),
        (
            "fan",
            FAN_SCRIPT_FIELDS,
            {
                "preset_modes": ["auto", "low", "medium", "high"],
                "state": "{{ 'on' }}",
            },
            (
                ("turn_on", {}),
                ("turn_off", {}),
                ("set_percentage", {"percentage": 25}),
                ("set_preset_mode", {"preset_mode": "auto"}),
                ("oscillate", {"oscillating": True}),
                ("set_direction", {"direction": "forward"}),
            ),
        ),
        (
            "light",
            LIGHT_SCRIPT_FIELDS,
            {
                "effect_list": "{{ ['foo', 'bar'] }}",
                "effect": "{{ 'foo' }}",
                "state": "{{ 'on' }}",
            },
            (
                ("turn_on", {"brightness": 1}),
                ("turn_off", {}),
                ("turn_on", {"color_temp_kelvin": 8130}),
                ("turn_on", {"hs_color": (360, 100)}),
                ("turn_on", {"rgb_color": (160, 78, 192)}),
                ("turn_on", {"rgbw_color": (160, 78, 192, 25)}),
                ("turn_on", {"rgbww_color": (160, 78, 192, 25, 55)}),
                ("turn_on", {"effect": "foo"}),
            ),
        ),
        (
            "lock",
            LOCK_SCRIPT_FIELDS,
            {
                "state": "{{ 'on' }}",
            },
            (
                ("lock", {}),
                ("unlock", {}),
                ("open", {}),
            ),
        ),
        (
            "number",
            NUMBER_SCRIPT_FIELDS,
            {"step": 1},
            (("set_value", {"value": 4}),),
        ),
        (
            "select",
            SELECT_SCRIPT_FIELDS,
            {
                "state": "{{ 'yes' }}",
                "options": "{{ ['test', 'yes', 'no'] }}",
            },
            (("select_option", {"option": "test"}),),
        ),
        (
            "switch",
            SWITCH_SCRIPT_FIELDS,
            {
                "state": "{{ 'on' }}",
            },
            (
                ("turn_on", {}),
                ("turn_off", {}),
            ),
        ),
        (
            "update",
            UPDATE_SCRIPT_FIELDS,
            {"installed_version": "{{ '2.0.0' }}", "latest_version": "{{ '3.0.0' }}"},
            (("install", {}),),
        ),
        (
            "vacuum",
            [
                service
                for service in VACUUM_SCRIPT_FIELDS
                if service != VACUUM_CLEAN_SEGMENTS
            ],
            {
                "fan_speeds": ["low", "medium", "high"],
                "state": "{{ 'on' }}",
            },
            (
                ("start", {}),
                ("pause", {}),
                ("stop", {}),
                ("return_to_base", {}),
                ("clean_spot", {}),
                ("locate", {}),
                ("set_fan_speed", {"fan_speed": "medium"}),
            ),
        ),
    ],
)
async def test_config_entry_device_actions(
    hass: HomeAssistant,
    domain: str,
    script_fields,
    extra_config: str,
    test_actions: tuple[tuple[str, dict], ...],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls: list,
) -> None:
    """Test device actions in config flow."""

    platform_setup, device_entry, entity_entry = await setup_mock_devices(
        hass, domain, device_registry, entity_registry
    )

    actions = make_mock_device_actions(
        script_fields, platform_setup, device_entry, entity_entry
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": platform_setup.object_id,
            "template_type": domain,
            **actions,
            **extra_config,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    for test_action, action_data in test_actions:
        call_count = len(calls)
        await hass.services.async_call(
            domain,
            test_action,
            {"entity_id": platform_setup.entity_id, **action_data},
            blocking=True,
        )
        assert_action(platform_setup, calls, call_count + 1, "fake_action")


async def test_platform_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_template_platform raises PlatformNotReady."""
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
