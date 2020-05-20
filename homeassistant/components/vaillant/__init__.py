"""The vaillant integration."""
import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS
from .hub import ApiHub, DomainData
from .service import SERVICES, VaillantServiceHandler

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the vaillant component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up vaillant from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    serial = entry.data.get(CONF_SERIAL_NUMBER)
    api: ApiHub = ApiHub(hass, username, password, serial)
    await api.authenticate()
    await api.update_system()

    hass.data[DOMAIN] = DomainData(api, entry)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    service_handler = VaillantServiceHandler(api, hass)
    for vaillant_service in SERVICES:
        schema = SERVICES[vaillant_service]["schema"]
        method_name = SERVICES[vaillant_service]["method"]
        method = getattr(service_handler, method_name)
        hass.services.async_register(DOMAIN, vaillant_service, method, schema=schema)

    async def logout(param):
        await api.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok
