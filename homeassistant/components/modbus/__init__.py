"""Support for Modbus."""

import logging

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .connection import async_get_temporary_unit, async_get_unit
from .const import DOMAIN
from .modbus import DATA_MODBUS_HUBS, ModbusHub, async_modbus_setup
from .schemas import CONFIG_SCHEMA

__all__ = [
    "CONFIG_SCHEMA",
    "ModbusHub",
    "async_get_temporary_unit",
    "async_get_unit",
    "get_hub",
]

_LOGGER = logging.getLogger(__name__)


def get_hub(hass: HomeAssistant, name: str) -> ModbusHub:
    """Return modbus hub with name.

    Deprecated. Use `async_get_unit` instead, which builds a connection from
    credentials the integration holds rather than attaching to a hub the user
    configured in YAML under a name the integration has to be told.
    """
    report_usage(
        "calls `modbus.get_hub`, which is deprecated in favour of "
        "`modbus.async_get_unit`. Collect the connection details in your own "
        "config flow and ask for a unit on them",
        breaks_in_ha_version="2027.10",
        core_behavior=ReportBehavior.IGNORE,
        core_integration_behavior=ReportBehavior.IGNORE,
        custom_integration_behavior=ReportBehavior.LOG,
        # get_hub is defined here, so its own frame is the first one the stack
        # walk meets. Without this it reports modbus every time, and the core
        # behavior above then silences the caller it was meant to name.
        exclude_integrations={DOMAIN},
    )
    return hass.data[DATA_MODBUS_HUBS][name]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Modbus component."""
    if DOMAIN not in config:
        return True

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload Modbus."""
        if DATA_MODBUS_HUBS not in hass.data:
            _LOGGER.error("Modbus cannot reload, because it was never loaded")
            return
        hubs = hass.data[DATA_MODBUS_HUBS]
        for hub in hubs.values():
            await hub.async_close()
        reset_platforms = async_get_platforms(hass, DOMAIN)
        for reset_platform in reset_platforms:
            _LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
            await reset_platform.async_reset()
        reload_config = await async_integration_yaml_config(hass, DOMAIN)
        if not reload_config:
            _LOGGER.debug("Modbus not present anymore")
            return
        _LOGGER.debug("Modbus reloading")
        await async_modbus_setup(hass, reload_config)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    return await async_modbus_setup(hass, config)
