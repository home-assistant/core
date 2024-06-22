"""Tests for ScreenLogic integration data processing."""

from unittest.mock import DEFAULT, patch

from screenlogicpy import ScreenLogicGateway

from homeassistant.components.screenlogic import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    DATA_MIN_ENTITY_CLEANUP,
    GATEWAY_DISCOVERY_IMPORT_PATH,
    MOCK_ADAPTER_MAC,
    MOCK_ADAPTER_NAME,
    stub_async_connect,
)

from tests.common import MockConfigEntry


async def test_async_cleanup_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup of unused entities."""
    mock_config_entry.add_to_hass(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
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

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=lambda *args, **kwargs: stub_async_connect(
                DATA_MIN_ENTITY_CLEANUP, *args, **kwargs
            ),
            is_connected=True,
            _async_connected_request=DEFAULT,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    deleted_entity = entity_registry.async_get(unused_entity.entity_id)
    assert deleted_entity is None
