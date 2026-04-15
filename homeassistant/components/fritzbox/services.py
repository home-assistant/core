"""Services for Fritz integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.const import ATTR_DEVICE_ID

from .const import DOMAIN
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"

SERVICE_SET_WINDOW_OPEN = "set_window_open"
SERVICE_SET_WINDOW_OPEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_DURATION): vol.Range(min=1, max=24 * 60 * 60),
    }
)
SERVICE_SET_WINDOW_CLOSE = "set_window_close"
SERVICE_SET_WINDOW_CLOSE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
    }
)
SERVICES = {
    SERVICE_SET_WINDOW_OPEN: SERVICE_SET_WINDOW_OPEN_SCHEMA,
    SERVICE_SET_WINDOW_CLOSE: SERVICE_SET_WINDOW_CLOSE_SCHEMA,
}


async def _service_handler(call: ServiceCall) -> None:
    """Call one of the Fritzbox services."""

    device_reg = dr.async_get(call.hass)

    for target_entry in await async_extract_config_entry_ids(call):
        coordinator: FritzboxDataUpdateCoordinator = target_entry.runtime_data
        if device_entry := device_reg.async_get(call.data[ATTR_DEVICE_ID]):
            for domain, ain in device_entry.identifiers:
                if domain == DOMAIN:
                    if call.service in [
                        SERVICE_SET_WINDOW_OPEN,
                        SERVICE_SET_WINDOW_CLOSE,
                    ]:
                        _LOGGER.debug("Executing service %s", call.service)
                        await call.hass.async_add_executor_job(
                            coordinator.fritz.set_window_open,
                            ain,
                            call.data.get(ATTR_DURATION) or 0,
                            True,
                        )
                        return


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Actions setup handler."""

    for service, schema in SERVICES.items():
        hass.services.async_register(DOMAIN, service, _service_handler, schema)
