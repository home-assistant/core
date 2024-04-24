"""Tests for the Rituals Perfume Genie integration."""
from unittest.mock import patch

import aiohttp

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    init_integration,
    mock_config_entry,
    mock_diffuser_v1_battery_cartridge,
)


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the Rituals configuration entry setup if connection to Rituals is missing."""
    config_entry = mock_config_entry(unique_id="id_123_not_ready")
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rituals_perfume_genie.Account.get_devices",
        side_effect=aiohttp.ClientError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_unload(hass: HomeAssistant) -> None:
    """Test the Rituals Perfume Genie configuration entry setup and unloading."""
    config_entry = mock_config_entry(unique_id="id_123_unload")
    await init_integration(hass, config_entry)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_entity_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the migration of unique IDs on config entry setup."""
    config_entry = mock_config_entry(unique_id="binary_sensor_test_diffuser_v1")

    # Pre-create old style unique IDs
    charging = entity_registry.async_get_or_create(
        "binary_sensor", DOMAIN, "lot123v1 Battery Charging", config_entry=config_entry
    )
    perfume_amount = entity_registry.async_get_or_create(
        "number", DOMAIN, "lot123v1 Perfume Amount", config_entry=config_entry
    )
    room_size = entity_registry.async_get_or_create(
        "select", DOMAIN, "lot123v1 Room Size", config_entry=config_entry
    )
    battery = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Battery", config_entry=config_entry
    )
    fill = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Fill", config_entry=config_entry
    )
    perfume = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Perfume", config_entry=config_entry
    )
    wifi = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Wifi", config_entry=config_entry
    )
    switch = entity_registry.async_get_or_create(
        "switch", DOMAIN, "lot123v1", config_entry=config_entry
    )

    # Set up integration
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])

    # Check that old style unique IDs have been migrated
    entry = entity_registry.async_get(charging.entity_id)
    assert entry.unique_id == "lot123v1-charging"

    entry = entity_registry.async_get(perfume_amount.entity_id)
    assert entry.unique_id == "lot123v1-perfume_amount"

    entry = entity_registry.async_get(room_size.entity_id)
    assert entry.unique_id == "lot123v1-room_size_square_meter"

    entry = entity_registry.async_get(battery.entity_id)
    assert entry.unique_id == "lot123v1-battery_percentage"

    entry = entity_registry.async_get(fill.entity_id)
    assert entry.unique_id == "lot123v1-fill"

    entry = entity_registry.async_get(perfume.entity_id)
    assert entry.unique_id == "lot123v1-perfume"

    entry = entity_registry.async_get(wifi.entity_id)
    assert entry.unique_id == "lot123v1-wifi_percentage"

    entry = entity_registry.async_get(switch.entity_id)
    assert entry.unique_id == "lot123v1-is_on"
