"""The IMGW-PIB integration."""

from __future__ import annotations

import logging

from aiohttp import ClientError
from imgw_pib import ImgwPib
from imgw_pib.exceptions import ApiError

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_PLATFORM
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DOMAIN
from .coordinator import ImgwPibConfigEntry, ImgwPibData, ImgwPibDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ImgwPibConfigEntry) -> bool:
    """Set up IMGW-PIB from a config entry."""
    station_id: str = entry.data[CONF_STATION_ID]

    _LOGGER.debug("Using hydrological station ID: %s", station_id)

    client_session = async_get_clientsession(hass)

    try:
        imgwpib = await ImgwPib.create(
            client_session,
            hydrological_station_id=station_id,
            hydrological_details=False,
        )
    except (ClientError, TimeoutError, ApiError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "entry": entry.title,
                "error": repr(err),
            },
        ) from err

    coordinator = ImgwPibDataUpdateCoordinator(hass, entry, imgwpib, station_id)
    await coordinator.async_config_entry_first_refresh()

    # Remove binary_sensor entities for which the endpoint has been blocked by IMGW-PIB API
    entity_reg = er.async_get(hass)
    for key in ("flood_warning", "flood_alarm"):
        if entity_id := entity_reg.async_get_entity_id(
            BINARY_SENSOR_PLATFORM, DOMAIN, f"{coordinator.station_id}_{key}"
        ):
            entity_reg.async_remove(entity_id)

    entry.runtime_data = ImgwPibData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImgwPibConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
