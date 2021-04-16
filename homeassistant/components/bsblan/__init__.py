"""The BSB-Lan integration."""
from datetime import timedelta

from bsblan import BSBLan, BSBLanConnectionError

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSKEY, DATA_BSBLAN_CLIENT, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BSB-Lan from a config entry."""

    session = async_get_clientsession(hass)
    bsblan = BSBLan(
        entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        session=session,
    )

    try:
        await bsblan.info()
    except BSBLanConnectionError as exception:
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_BSBLAN_CLIENT: bsblan}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMATE_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BSBLan config entry."""

    await hass.config_entries.async_forward_entry_unload(entry, CLIMATE_DOMAIN)

    # Cleanup
    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
