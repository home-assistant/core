"""Tests for ScreenLogic integration data processing."""
from unittest.mock import patch

from homeassistant.components.screenlogic import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_ADAPTER_MAC, MOCK_ADAPTER_NAME

from tests.common import MockConfigEntry


async def test_async_cleanup_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cleanup_gateway,
) -> None:
    """Test cleanup of unused entities."""

    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_ADAPTER_MAC)},
    )

    TEST_UNUSED_ENTRY = {
        "domain": SENSOR_DOMAIN,
        "platform": DOMAIN,
        "unique_id": f"{MOCK_ADAPTER_MAC}_saturation",
        "suggested_object_id": f"{MOCK_ADAPTER_NAME} Saturation Index",
        "disabled_by": None,
        "has_entity_name": True,
        "original_name": "Saturation Index",
    }

    unused_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **TEST_UNUSED_ENTRY, device_id=device.id, config_entry=mock_config_entry
    )

    assert unused_entity
    assert unused_entity.unique_id == TEST_UNUSED_ENTRY["unique_id"]

    with patch(
        "homeassistant.components.screenlogic.coordinator.async_discover_gateways_by_unique_id",
        return_value={},
    ), patch(
        "homeassistant.components.screenlogic.ScreenLogicGateway",
        return_value=mock_cleanup_gateway,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    deleted_entity = entity_registry.async_get(unused_entity.entity_id)
    assert deleted_entity is None
