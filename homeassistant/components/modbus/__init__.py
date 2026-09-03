"""Support for Modbus."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.typing import ConfigType

from .connection import async_get_temporary_unit, async_get_unit
from .const import DATA_MODBUS_HUBS, DOMAIN
from .modbus import ModbusHub, async_modbus_setup
from .schemas import CONFIG_SCHEMA
from .services import async_setup_services

__all__ = [
    "CONFIG_SCHEMA",
    "ModbusHub",
    "async_get_temporary_unit",
    "async_get_unit",
    "get_hub",
]


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

    async_setup_services(hass)

    return await async_modbus_setup(hass, config)
