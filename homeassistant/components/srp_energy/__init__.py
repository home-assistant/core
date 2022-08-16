"""The SRP Energy integration."""
from __future__ import annotations

import logging

from srpenergy.client import SrpEnergyClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import (  # noqa: F401
    ATTRIBUTION,
    CONF_IS_TOU,
    DEVICE_NAME_ENERGY,
    DEVICE_NAME_PRICE,
    DOMAIN,
    PHOENIX_TIME_ZONE,
    TIME_DELTA_BETWEEN_API_UPDATES,
    TIME_DELTA_BETWEEN_UPDATES,
)
from .coordinator import SrpApiCoordinator, SrpCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SRP Energy component from a config entry."""
    api_account_id: str = entry.data[CONF_ID]
    api_username: str = entry.data[CONF_USERNAME]
    api_password: str = entry.data[CONF_PASSWORD]
    name: str = entry.data[CONF_NAME]
    is_tou: bool = entry.data.get(CONF_IS_TOU, False)

    _LOGGER.debug(
        "%s Using account_id %s, time of use: %s", name, api_account_id, is_tou
    )

    api_instance = SrpEnergyClient(
        api_account_id,
        api_username,
        api_password,
    )
    api_coordinator = SrpApiCoordinator(hass, api_instance, name, is_tou)
    coordinator = SrpCoordinator(
        hass=hass, api=api_instance, api_coordiator=api_coordinator, name=name
    )
    await api_coordinator.async_config_entry_first_refresh()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
