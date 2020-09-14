"""Config flow for Raspberry Pi Power Supply Checker."""
from rpi_bad_power import new_under_voltage

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_supported(hass: HomeAssistant) -> bool:
    """Return if the system supports under voltage detection."""
    under_voltage = await hass.async_add_executor_job(new_under_voltage)
    return under_voltage is not None


config_entry_flow.register_discovery_flow(
    DOMAIN,
    "Raspberry Pi Power Supply Checker",
    _async_supported,
    config_entries.CONN_CLASS_LOCAL_POLL,
)
