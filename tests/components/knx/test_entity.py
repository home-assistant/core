"""KNX base entity tests."""

from typing import Any

import pytest

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.const import STATE_OFF, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    expected_friendly_name: str,
) -> None:
    """Test KNX entity id and name setting from YAML configuration."""
    await knx.setup_integration({Platform.SWITCH: config})
    knx.assert_state(
        expected_entity_id,
        STATE_OFF,
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
