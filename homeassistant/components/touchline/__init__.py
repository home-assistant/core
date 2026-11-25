"""The touchline component."""

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TouchlineConfigEntry, TouchlineCoordinator

PLATFORMS = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
    """Set up touchline from a config entry."""
    _LOGGER.debug(
        "Touchline entry id: %s Unique id: %s", entry.entry_id, entry.unique_id
    )
    coordinator = TouchlineCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    if TYPE_CHECKING:
        assert entry.unique_id is not None
    controller = coordinator.controller_status
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        connections=(
            {(dr.CONNECTION_NETWORK_MAC, controller.mac_address)}
            if controller.mac_address
            else set()
        ),
        manufacturer="Roth",
        model="Touchline controller",
        name=controller.hostname,
        serial_number=controller.unique_id,
        sw_version=controller.stm_app_version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
    """Unload a touchline config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: TouchlineConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow removing a thermostat that the controller no longer reports."""
    return not any(
        identifier[0] == DOMAIN
        and (
            identifier[1] == entry.unique_id or identifier[1] in entry.runtime_data.data
        )
        for identifier in device_entry.identifiers
    )
