"""The Homey Energy Dongle integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import (
    HomeyEnergyDongleConfigEntry,
    HomeyEnergyDongleCoordinator,
    meters,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: HomeyEnergyDongleConfigEntry
) -> None:
    """Set up Homey Energy Dongle from a config entry."""
    coordinator = HomeyEnergyDongleCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Registered up front so the meters can link to it.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Homey",
        model="Homey Energy Dongle",
        name=entry.title,
    )

    entry.async_create_background_task(
        hass, coordinator.async_listen(), f"{DOMAIN}_{entry.entry_id}_listen"
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeyEnergyDongleConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: HomeyEnergyDongleConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing meters that are missing from the latest telegram.

    Wireless meters can drop out of a telegram for a while, and a replaced
    meter stays as a device, so neither is removed automatically.
    """
    present = {entry.entry_id}
    if entry.state is ConfigEntryState.LOADED:
        present.update(meters(entry.runtime_data.data, entry))
    return not any(
        identifier in present
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    )
