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
                    "device": {"id": "living_room", "name": "Living room"},
                },
                {
                    "default_entity_id": "switch.b",
                    KNX_ADDRESS: "1/1/2",
                    "device": {"id": "living_room", "name": "Living room"},
                },
                {
                    "default_entity_id": "switch.c",
                    KNX_ADDRESS: "1/1/3",
                    "device": {"id": "bedroom"},  # name is optional
                },
                {"default_entity_id": "switch.d", KNX_ADDRESS: "1/1/4"},
            ]
        }
    )

    entity_a = entity_registry.async_get("switch.a")
    entity_b = entity_registry.async_get("switch.b")
    entity_c = entity_registry.async_get("switch.c")
    entity_d = entity_registry.async_get("switch.d")

    assert entity_a.device_id is not None
    assert entity_a.device_id == entity_b.device_id
    assert entity_c.device_id not in (None, entity_a.device_id)
    assert entity_d.device_id is None

    device = device_registry.async_get(entity_a.device_id)
    assert device.name == "Living room"
    assert device.manufacturer == "KNX"
    assert (DOMAIN, "living_room") in device.identifiers

    # `name` is optional; the device is still created keyed by its `id`.
    bedroom = device_registry.async_get(entity_c.device_id)
    assert (DOMAIN, "bedroom") in bedroom.identifiers


@pytest.mark.parametrize(
    ("config", "expected_friendly_name"),
    [
        (
            {
                "name": "Ceiling light",
                KNX_ADDRESS: "1/1/1",
                "device": {"id": "kitchen", "name": "Kitchen"},
            },
            "Kitchen Ceiling light",
        ),
        (
            {
                KNX_ADDRESS: "1/1/1",
                "device": {"id": "kitchen", "name": "Kitchen"},
            },
            "Kitchen",  # no entity name: entity is the device's main feature
        ),
        (
            {"name": "Ceiling light", KNX_ADDRESS: "1/1/1"},
            "Ceiling light",  # no device: name is shown verbatim, as before
        ),
    ],
)
async def test_yaml_entity_device_naming(
    hass: HomeAssistant,
    knx: KNXTestKit,
    config: dict[str, Any],
    expected_friendly_name: str,
) -> None:
    """An entity on a device uses has_entity_name naming, like a UI entity."""
    await knx.setup_integration({Platform.SWITCH: config})
    states = hass.states.async_all("switch")
    assert len(states) == 1
    assert states[0].attributes["friendly_name"] == expected_friendly_name


@pytest.mark.parametrize(
    ("device_id", "expected_identifier"),
    [
        ("Living Room", "living_room"),
        ("living room", "living_room"),
        (" living_room ", "living_room"),
        # A UI device identifier is preserved verbatim, not lower-cased.
        ("knx_vdev_ABC123", "knx_vdev_ABC123"),
        # Surrounding whitespace is stripped before the UI-prefix check.
        (" knx_vdev_ABC123 ", "knx_vdev_ABC123"),
    ],
)
async def test_yaml_device_id_normalization(
    hass: HomeAssistant,
    knx: KNXTestKit,
    device_registry: dr.DeviceRegistry,
    device_id: str,
    expected_identifier: str,
) -> None:
    """A YAML device `id` is slugified unless it is a UI device identifier."""
    await knx.setup_integration(
        {
            Platform.SWITCH: {
                "name": "test",
                KNX_ADDRESS: "1/1/1",
                "device": {"id": device_id},
            }
        }
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, expected_identifier), knx.mock_config_entry.entry_id
    )
