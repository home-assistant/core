"""The tests for template helpers."""

from unittest.mock import AsyncMock, Mock

import pytest
import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
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
    TemplatePlatformSetup,
    assert_action,
    async_trigger,
    make_test_trigger,
    setup_entity,
)

from tests.common import MockConfigEntry, mock_platform


async def _setup_mock_devices(
    hass: HomeAssistant,
    domain: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> tuple[TemplatePlatformSetup, dr.DeviceEntry, er.RegistryEntry]:
    FAKE_DOMAIN = "fake_integration"

    hass.config.components.add(FAKE_DOMAIN)

    async def _async_get_actions(
        hass: HomeAssistant, device_id: str
    ) -> list[dict[str, str]]:
        """List device actions."""
        return await toggle_entity.async_get_actions(hass, device_id, FAKE_DOMAIN)

    mock_platform(
        hass,
        f"{FAKE_DOMAIN}.device_action",
        Mock(
            ACTION_SCHEMA=toggle_entity.ACTION_SCHEMA.extend(
                {vol.Required("domain"): FAKE_DOMAIN}
            ),
            async_get_actions=_async_get_actions,
            async_call_action_from_config=AsyncMock(),
            spec=[
                "ACTION_SCHEMA",
                "async_get_actions",
                "async_call_action_from_config",
            ],
        ),
    )
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    await hass.async_block_till_done()

    platform_setup = TemplatePlatformSetup(
        domain, "test_entity", make_test_trigger("sensor.trigger")
    )
    return (platform_setup, device_entry, entity_entry)


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

    platform_setup, device_entry, entity_entry = await _setup_mock_devices(
        hass, domain, device_registry, entity_registry
    )

    actions = {
        action: [
            {
                "action": "test.automation",
                "data": {
                    "action": "fake_action",
                    "caller": platform_setup.entity_id,
                },
            },
            {
                "domain": "fake_integration",
                "type": "turn_on",
                "device_id": device_entry.id,
                "entity_id": entity_entry.id,
                "metadata": {"secondary": False},
            },
        ]
        for action in script_fields
    }

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

    platform_setup, device_entry, entity_entry = await _setup_mock_devices(
        hass, domain, device_registry, entity_registry
    )

    actions = {
        action: [
            {
                "action": "test.automation",
                "data": {
                    "action": "fake_action",
                    "caller": platform_setup.entity_id,
                },
            },
            {
                "domain": "fake_integration",
                "type": "turn_on",
                "device_id": device_entry.id,
                "entity_id": entity_entry.id,
                "metadata": {"secondary": False},
            },
        ]
        for action in script_fields
    }

    template_config_entry = MockConfigEntry(
        data={},
        domain="template",
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
