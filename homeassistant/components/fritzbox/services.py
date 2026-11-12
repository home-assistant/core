"""Services for FRITZ!Box SmartHome integration."""

from enum import StrEnum

import probatio

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, service
from homeassistant.helpers.service import verify_domain_control

from .const import DOMAIN, LOGGER
from .coordinator import FritzboxConfigEntry


class FritzboxService(StrEnum):
    """Fritzbox services."""

    SET_WINDOW_OPEN = "set_window_open"
    SET_WINDOW_CLOSE = "set_window_close"


class FritzboxServiceArgument(StrEnum):
    """Fritzbox services arguments."""

    DURATION = "duration"


SERVICE_SET_WINDOW_OPEN_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): str,
        probatio.Required(FritzboxServiceArgument.DURATION): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=24 * 60 * 60)
        ),
    }
)
SERVICE_SET_WINDOW_CLOSE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): str,
    }
)
SERVICES = {
    FritzboxService.SET_WINDOW_OPEN: SERVICE_SET_WINDOW_OPEN_SCHEMA,
    FritzboxService.SET_WINDOW_CLOSE: SERVICE_SET_WINDOW_CLOSE_SCHEMA,
}


@verify_domain_control(DOMAIN)
async def _service_handler(call: ServiceCall) -> None:
    """Call one of the Fritzbox services."""
    assert call.service in [
        FritzboxService.SET_WINDOW_OPEN,
        FritzboxService.SET_WINDOW_CLOSE,
    ]

    enttiy_reg = er.async_get(call.hass)
    entity_id = enttiy_reg.async_get(call.data[ATTR_ENTITY_ID])

    assert entity_id is not None
    assert entity_id.platform == DOMAIN
    assert entity_id.domain == Platform.CLIMATE
    assert entity_id.device_id is not None

    device_reg = dr.async_get(call.hass)
    if device_entry := device_reg.async_get(entity_id.device_id):
        for domain, ain in device_entry.identifiers:
            assert domain == DOMAIN

            LOGGER.debug("Executing service %s", call.service)
            config_entry: FritzboxConfigEntry = service.async_get_config_entry(
                call.hass, DOMAIN, None
            )
            coordinator = config_entry.runtime_data
            await call.hass.async_add_executor_job(
                coordinator.fritz.set_window_open,
                ain,
                call.data.get(FritzboxServiceArgument.DURATION, 0),
                True,
            )
            await coordinator.async_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Actions setup handler."""

    for service_, schema in SERVICES.items():
        hass.services.async_register(DOMAIN, service_, _service_handler, schema)
