"""
Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/core/issues/20957
"""
from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_aqara_gateway_setup(hass):
    """Test that a Aqara Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_gateway.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    sensors = [
        (
            "alarm_control_panel.aqara_hub_1563",
            "homekit-0000000123456789-66304",
            "Aqara Hub-1563",
            SUPPORT_ALARM_ARM_NIGHT | SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY,
            None,
        ),
        (
            "light.aqara_hub_1563",
            "homekit-0000000123456789-65792",
            "Aqara Hub-1563",
            SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
            None,
        ),
        (
            "number.aqara_hub_1563_volume",
            "homekit-0000000123456789-aid:1-sid:65536-cid:65541",
            "Aqara Hub-1563 Volume",
            None,
            EntityCategory.CONFIG,
        ),
        (
            "switch.aqara_hub_1563_pairing_mode",
            "homekit-0000000123456789-aid:1-sid:65536-cid:65538",
            "Aqara Hub-1563 Pairing Mode",
            None,
            EntityCategory.CONFIG,
        ),
    ]

    device_ids = set()

    for (entity_id, unique_id, friendly_name, supported_features, category) in sensors:
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == unique_id
        assert entry.entity_category == category

        helper = Helper(
            hass,
            entity_id,
            pairing,
            accessories[0],
            config_entry,
        )
        state = await helper.poll_and_get_state()
        assert state.attributes["friendly_name"] == friendly_name
        assert state.attributes.get("supported_features") == supported_features

        device = device_registry.async_get(entry.device_id)
        assert device.manufacturer == "Aqara"
        assert device.name == "Aqara Hub-1563"
        assert device.model == "ZHWA11LM"
        assert device.sw_version == "1.4.7"
        assert device.via_device_id is None

        device_ids.add(entry.device_id)

    # All entities should be part of same device
    assert len(device_ids) == 1


async def test_aqara_gateway_e1_setup(hass):
    """Test that an Aqara E1 Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_e1.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    sensors = [
        (
            "alarm_control_panel.aqara_hub_e1_00a0",
            "homekit-00aa00000a0-16",
            "Aqara-Hub-E1-00A0",
            SUPPORT_ALARM_ARM_NIGHT | SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY,
            None,
        ),
        (
            "number.aqara_hub_e1_00a0_volume",
            "homekit-00aa00000a0-aid:1-sid:17-cid:1114116",
            "Aqara-Hub-E1-00A0 Volume",
            None,
            EntityCategory.CONFIG,
        ),
        (
            "switch.aqara_hub_e1_00a0_pairing_mode",
            "homekit-00aa00000a0-aid:1-sid:17-cid:1114117",
            "Aqara-Hub-E1-00A0 Pairing Mode",
            None,
            EntityCategory.CONFIG,
        ),
    ]

    device_ids = set()

    for (entity_id, unique_id, friendly_name, supported_features, category) in sensors:
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == unique_id
        assert entry.entity_category == category

        helper = Helper(
            hass,
            entity_id,
            pairing,
            accessories[0],
            config_entry,
        )
        state = await helper.poll_and_get_state()
        assert state.attributes["friendly_name"] == friendly_name
        assert state.attributes.get("supported_features") == supported_features

        device = device_registry.async_get(entry.device_id)
        assert device.manufacturer == "Aqara"
        assert device.name == "Aqara-Hub-E1-00A0"
        assert device.model == "HE1-G01"
        assert device.sw_version == "3.3.0"
        assert device.via_device_id is None

        device_ids.add(entry.device_id)

    # All entities should be part of same device
    assert len(device_ids) == 1
