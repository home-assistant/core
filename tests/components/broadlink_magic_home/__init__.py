"""Tests for the Broadlink Magic Home integration."""

from broadlink_magic import MSG_HEARTBEAT, pack_message
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.broadlink_magic_home.coordinator import FamilyCoordinator
from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> FamilyCoordinator:
    """Set up the family entry and bring its first gateway online."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    coordinator.async_set_updated_data(coordinator.gateway_set)
    await hass.async_block_till_done()
    return coordinator
