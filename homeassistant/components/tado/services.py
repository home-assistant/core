"""Services for the Tado integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector, service

from .const import ATTR_MESSAGE, DOMAIN
from .coordinator import TadoConfigEntry

_LOGGER = logging.getLogger(__name__)


class TadoService(StrEnum):
    """Store keys for Tado services."""

    ADD_METER_READING = "add_meter_reading"


class TadoServiceArgument(StrEnum):
    """Store keys for Tado service arguments."""

    CONFIG_ENTRY = "config_entry"
    READING = "reading"


SCHEMA_ADD_METER_READING = probatio.Schema(
    {
        probatio.Required(
            TadoServiceArgument.CONFIG_ENTRY
        ): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        probatio.Required(TadoServiceArgument.READING): probatio.Coerce(int),
    }
)


async def _add_meter_reading(call: ServiceCall) -> None:
    """Send meter reading to Tado."""
    reading: int = call.data[TadoServiceArgument.READING]
    _LOGGER.debug("Add meter reading %s", reading)

    entry: TadoConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[TadoServiceArgument.CONFIG_ENTRY]
    )

    coordinator = entry.runtime_data
    response: dict = await coordinator.set_meter_reading(
        call.data[TadoServiceArgument.READING]
    )

    if ATTR_MESSAGE in response:
        raise HomeAssistantError(response[ATTR_MESSAGE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tado integration."""

    hass.services.async_register(
        DOMAIN,
        TadoService.ADD_METER_READING,
        _add_meter_reading,
        SCHEMA_ADD_METER_READING,
    )
