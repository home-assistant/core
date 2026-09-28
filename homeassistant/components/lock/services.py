"""Services for the Lock integration."""

import probatio

from homeassistant.const import ATTR_CODE, SERVICE_LOCK, SERVICE_OPEN, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, LockEntityFeature

LOCK_SERVICE_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(ATTR_CODE): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the lock services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_UNLOCK, LOCK_SERVICE_SCHEMA, "async_handle_unlock_service"
    )
    component.async_register_entity_service(
        SERVICE_LOCK, LOCK_SERVICE_SCHEMA, "async_handle_lock_service"
    )
    component.async_register_entity_service(
        SERVICE_OPEN,
        LOCK_SERVICE_SCHEMA,
        "async_handle_open_service",
        [LockEntityFeature.OPEN],
    )
