"""Support for Modbus."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORM_LIST
from .modbus import (
    DATA_MODBUS_HUBS,
    ModbusHub as ModbusHub,
    async_modbus_setup,
    get_hub as get_hub,
)
from .schemas import CONFIG_SCHEMA  # noqa: F401

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Modbus component."""
    if DOMAIN not in config:
        return True

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload Modbus."""
        reload_config = await async_integration_yaml_config(hass, DOMAIN)

        for entry in list(hass.config_entries.async_entries(DOMAIN)):
            await hass.config_entries.async_remove(entry.entry_id)

        if not reload_config:
            _LOGGER.debug("Modbus not present anymore")
            return

        _LOGGER.debug("Modbus reloading")
        await async_modbus_setup(hass, reload_config)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    return await async_modbus_setup(hass, config)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Modbus hub from a config entry."""
    hub = ModbusHub(hass, dict(entry.data))
    name = entry.data[CONF_NAME]

    if DATA_MODBUS_HUBS not in hass.data:
        hass.data[DATA_MODBUS_HUBS] = {}
    hass.data[DATA_MODBUS_HUBS][name] = hub

    if not await hub.async_setup():
        hass.data[DATA_MODBUS_HUBS].pop(name)
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM_LIST)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Modbus hub config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORM_LIST)
    if unload_ok:
        name = entry.data[CONF_NAME]
        hub = hass.data[DATA_MODBUS_HUBS].pop(name)
        await hub.async_close()
    return unload_ok
