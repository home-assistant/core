"""KNX base entity tests."""

from typing import Any

import pytest

from homeassistant.components.knx.const import DOMAIN, KNX_ADDRESS
from homeassistant.const import STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import KNXTestKit


@pytest.mark.parametrize(
    ("config", "expected_entity_id", "expected_friendly_name"),
    [
        (
            {
                "name": "test",
                KNX_ADDRESS: "1/2/3",
            },
            "switch.test",
            "test",
        ),
        (
            {
                KNX_ADDRESS: "1/2/3",
            },
            "switch.knx_1_2_3",  # generated from unique_id
            None,
        ),
        (
            {
                "name": "",
                KNX_ADDRESS: "1/2/3",
            },
            "switch.knx_1_2_3",  # generated from unique_id
            None,
        ),
        (
            {
                "default_entity_id": "switch.test_default_entity_id",
                KNX_ADDRESS: "1/2/3",
            },
            "switch.test_default_entity_id",
            None,
        ),
        (
            {
                "name": "my_test_name",
                "default_entity_id": "switch.test_default_entity_id",
                KNX_ADDRESS: "1/2/3",
            },
            "switch.test_default_entity_id",
            "my_test_name",
        ),
    ],
)
async def test_yaml_entity_naming(
    hass: HomeAssistant,
    knx: KNXTestKit,
    config: dict[str, Any],
    expected_entity_id: str,
    expected_friendly_name: str | None,
) -> None:
    """Test KNX entity id and name setting from YAML configuration."""
    await knx.setup_integration({Platform.SWITCH: config})
    knx.assert_state(
        expected_entity_id,
        STATE_UNKNOWN,
        friendly_name=expected_friendly_name,
    )


@pytest.mark.parametrize(
    ("config", "expected_entity_category"),
    [
        (
            {},
            None,
        ),
        (
            {
                "entity_category": "diagnostic",
            },
            EntityCategory.DIAGNOSTIC,
        ),
        (
            {
                "entity_category": "config",
            },
            EntityCategory.CONFIG,
        ),
    ],
)
async def test_yaml_entity_category(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    config: dict[str, Any],
    expected_entity_category: EntityCategory | None,
) -> None:
    """Test KNX entity category setting from YAML configuration."""
    await knx.setup_integration(
        {
            Platform.SWITCH: [
                {
                    "default_entity_id": "switch.test",
                    KNX_ADDRESS: "1/1/1",
                    **config,
                },
            ]
        }
    )

    entity = entity_registry.async_get("switch.test")
    assert entity.entity_category is expected_entity_category


async def test_yaml_entity_device_grouping(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Entities sharing a `device` name are grouped into a single device."""
    await knx.setup_integration(
        {
            Platform.SWITCH: [
                {
                    "default_entity_id": "switch.a",
                    KNX_ADDRESS: "1/1/1",
                    "device": "Living room",
                },
                {
                    "default_entity_id": "switch.b",
                    KNX_ADDRESS: "1/1/2",
                    "device": "Living room",
                },
                {
                    "default_entity_id": "switch.c",
                    KNX_ADDRESS: "1/1/3",
                    "device": "Bedroom",
                },
                {"default_entity_id": "switch.d", KNX_ADDRESS: "1/1/4"},
            ]
        }
    )

    entity_a = entity_registry.async_get("switch.a")
    entity_b = entity_registry.async_get("switch.b")
    entity_c = entity_registry.async_get("switch.c")
    entity_d = entity_registry.async_get("switch.d")

    # Same `device` name shares one device; a different name is a separate device.
    assert entity_a.device_id is not None
    assert entity_a.device_id == entity_b.device_id
    assert entity_c.device_id not in (None, entity_a.device_id)
    # Without `device` the entity is not attached to any device.
    assert entity_d.device_id is None

    device = device_registry.async_get(entity_a.device_id)
    assert device.name == "Living room"
    assert device.manufacturer == "KNX"
    assert (DOMAIN, "Living room") in device.identifiers
