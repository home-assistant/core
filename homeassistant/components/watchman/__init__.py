"""Component to integrate Kingspan Watchman SENSiT with Home Assistant."""

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    SENSiTConfigEntry,
    SENSiTDataUpdateCoordinator,
    async_create_repair_issue,
    async_delete_repair_issue,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Set up this integration using UI."""
    username = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)

    if not username or not password:
        async_create_repair_issue(hass, config_entry)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="credentials_not_set",
        )

    coordinator = SENSiTDataUpdateCoordinator(
        hass,
        config_entry=config_entry,
        httpx_client=get_async_client(hass),
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        async_delete_repair_issue(hass, config_entry)
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="no_data")

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    async_delete_repair_issue(hass, config_entry)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Handle removal of an entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    async_delete_repair_issue(hass, config_entry)


async def async_remove_config_entry_device(
    _hass: HomeAssistant,
    config_entry: SENSiTConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow manual removal of stale devices via the UI."""
    if not hasattr(config_entry, "runtime_data"):
        return False
    coordinator = config_entry.runtime_data
    active_serials = {tank.serial_number for tank in coordinator.data}

    domain_serials = {
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    }
    if not domain_serials.isdisjoint(active_serials):
        return False

    # Clear discovery tracking so the tanks can be recreated if they come back
    coordinator.added_tanks.difference_update(domain_serials)

    return True
