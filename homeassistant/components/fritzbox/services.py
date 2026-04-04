"""Services for Fritz integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARAM_DEVICE_ID = "device_id"
PARAM_DURATION = "duration"

SERVICE_SET_WINDOW_OPEN = "set_window_open"
SERVICE_SET_WINDOW_OPEN_SCHEMA = vol.Schema(
    {
        vol.Required(PARAM_DEVICE_ID): str,
        vol.Required(PARAM_DURATION): vol.Range(min=1, max=24 * 60 * 60),
    }
)
SERVICE_SET_WINDOW_CLOSE = "set_window_close"
SERVICE_SET_WINDOW_CLOSE_SCHEMA = vol.Schema(
    {
        vol.Required(PARAM_DEVICE_ID): str,
    }
)
SERVICES = {
    SERVICE_SET_WINDOW_OPEN: SERVICE_SET_WINDOW_OPEN_SCHEMA,
    SERVICE_SET_WINDOW_CLOSE: SERVICE_SET_WINDOW_CLOSE_SCHEMA,
}


async def _service_handler(call: ServiceCall) -> None:
    """Call one of the Fritzbox services."""

    target_entries: list[FritzboxConfigEntry] = (
        call.hass.config_entries.async_loaded_entries(DOMAIN)
    )

    device_reg = dr.async_get(call.hass)

    for target_entry in target_entries:
        coordinator: FritzboxDataUpdateCoordinator = target_entry.runtime_data
        for device_entry in dr.async_entries_for_config_entry(
            device_reg, target_entry.entry_id
        ):
            if device_entry.id == call.data.get(PARAM_DEVICE_ID):
                for domain, ain in device_entry.identifiers:
                    assert domain == DOMAIN
                    if call.service in [
                        SERVICE_SET_WINDOW_OPEN,
                        SERVICE_SET_WINDOW_CLOSE,
                    ]:
                        param = {
                            SERVICE_SET_WINDOW_OPEN: call.data.get(PARAM_DURATION),
                            SERVICE_SET_WINDOW_CLOSE: 0,
                        }

                        _LOGGER.debug("Executing service %s", call.service)
                        await call.hass.async_add_executor_job(
                            coordinator.fritz.set_window_open,
                            ain,
                            param[call.service],
                            True,
                        )
                        return


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Actions setup handler."""

    for service, schema in SERVICES.items():
        hass.services.async_register(DOMAIN, service, _service_handler, schema)
