"""The Fujitsu HVAC (based on Ayla IOT) integration."""

from __future__ import annotations

from contextlib import suppress

from ayla_iot_unofficial import new_ayla_api
from ayla_iot_unofficial.fujitsu_consts import FGLAIR_APP_CREDENTIALS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import API_TIMEOUT, CONF_REGION, CONF_REGION_EUROPE
from .coordinator import FGLairCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type FGLairConfigEntry = ConfigEntry[FGLairCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FGLairConfigEntry) -> bool:
    """Set up Fujitsu HVAC (based on Ayla IOT) from a config entry."""
    app_id, app_secret = FGLAIR_APP_CREDENTIALS[entry.data[CONF_REGION]]
    api = new_ayla_api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        app_id,
        app_secret,
        europe=entry.data[CONF_REGION] == CONF_REGION_EUROPE["value"],
        websession=aiohttp_client.async_get_clientsession(hass),
        timeout=API_TIMEOUT,
    )

    coordinator = FGLairCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FGLairConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    with suppress(TimeoutError):
        await entry.runtime_data.api.async_sign_out()

    return unload_ok
