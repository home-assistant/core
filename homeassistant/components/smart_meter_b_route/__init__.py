"""The Smart Meter B Route integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BRouteUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

type BRouteConfigEntry = ConfigEntry[BRouteUpdateCoordinator]


def is_duplicate(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Filter duplicate entries."""
    existing_entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    entry_bid = entry.data[CONF_ID]
    for existing_entry in existing_entries:
        existing_entry_bid = existing_entry.data[CONF_ID]
        if (
            existing_entry_bid == entry_bid
            and existing_entry.unique_id != entry.unique_id
        ):
            _LOGGER.warning(
                "Duplicate entry found (Skipping): existing_entry.unique_id=%s, entry.unique_id=%s, entry.runtime_data.bid=%s",
                existing_entry.unique_id,
                entry.unique_id,
                entry_bid,
            )
            return True
    return False


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Set up Smart Meter B Route from a config entry."""
    if is_duplicate(hass, entry):
        return False

    device = entry.data[CONF_DEVICE]
    bid = entry.data[CONF_ID]
    password = entry.data[CONF_PASSWORD]
    coordinator = BRouteUpdateCoordinator(hass, device, bid, password)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
