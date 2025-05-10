import logging
from typing import Tuple

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from frisquet_connect.const import DOMAIN
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)


_LOGGER = logging.getLogger(__name__)


async def async_initialize_entity(
    hass: HomeAssistant, entry: ConfigEntry, entity_name: str
) -> Tuple[bool, FrisquetConnectCoordinator]:
    _LOGGER.debug(f"Initializing entity '{entity_name}'")

    initialization_result = True
    coordinator: FrisquetConnectCoordinator = None

    if entry.data.get("site_id") is None:
        _LOGGER.error(
            "No site_id found in the config entry. Please configure the device"
        )
        initialization_result = False
    else:
        coordinator: FrisquetConnectCoordinator = hass.data[DOMAIN][entry.unique_id]

        if not coordinator.is_site_loaded:
            _LOGGER.error("Site not found")
            initialization_result = False

    _LOGGER.debug(
        f"Pre-initialization result for entity '{entity_name}' : {initialization_result}"
    )

    return (initialization_result, coordinator)
