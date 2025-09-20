"""Support for Modbus."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import MODBUS_DOMAIN
from .modbus import DATA_MODBUS_HUBS, ModbusHub, async_modbus_setup
from .schema_old import CONFIG_SCHEMA_OLD

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {MODBUS_DOMAIN: CONFIG_SCHEMA_OLD},
)


def get_hub(hass: HomeAssistant, name: str) -> ModbusHub:
    """Return modbus hub with name."""
    return hass.data[DATA_MODBUS_HUBS][name]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Modbus component."""
    if MODBUS_DOMAIN not in config:
        return True

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload Modbus."""
        if DATA_MODBUS_HUBS not in hass.data:
            _LOGGER.error("Modbus cannot reload, because it was never loaded")
            return
        hubs = hass.data[DATA_MODBUS_HUBS]
        for hub in hubs.values():
            await hub.async_close()
        reset_platforms = async_get_platforms(hass, MODBUS_DOMAIN)
        for reset_platform in reset_platforms:
            _LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
            await reset_platform.async_reset()
        reload_config = await async_integration_yaml_config(hass, MODBUS_DOMAIN)
        if not reload_config:
            _LOGGER.debug("Modbus not present anymore")
            return
        _LOGGER.debug("Modbus reloading")
        await async_modbus_setup(hass, reload_config)

    async_register_admin_service(hass, MODBUS_DOMAIN, SERVICE_RELOAD, _reload_config)

    return await async_modbus_setup(hass, config)
