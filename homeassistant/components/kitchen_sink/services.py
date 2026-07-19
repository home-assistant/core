"""Services for the Everything but the Kitchen Sink integration."""

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SCHEMA_SERVICE_TEST_SERVICE_1 = vol.Schema(
    {
        vol.Required("field_1"): vol.Coerce(int),
        vol.Required("field_2"): vol.In(["off", "auto", "cool"]),
        vol.Optional("field_3"): vol.Coerce(int),
        vol.Optional("field_4"): vol.In(["forward", "reverse"]),
    }
)

SERVICE_TEST_SERVICE_1 = "test_service_1"
SERVICE_SET_TRACKER_LOCATION = "set_tracker_location"
SERVICE_SET_SCANNER_CONNECTED = "set_scanner_connected"

ATTR_ACCURACY = "accuracy"
ATTR_CONNECTED = "connected"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Kitchen Sink integration."""

    @callback
    def service_handler(call: ServiceCall) -> ServiceResponse:
        """Do nothing."""
        return None

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_SERVICE_1,
        service_handler,
        SCHEMA_SERVICE_TEST_SERVICE_1,
        description_placeholders={
            "meep_1": "foo",
            "meep_2": "bar",
            "meep_3": "beer",
            "meep_4": "milk",
            "meep_5": "https://example.com",
        },
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TRACKER_LOCATION,
        entity_domain=DEVICE_TRACKER_DOMAIN,
        schema={
            vol.Required(ATTR_LATITUDE): cv.latitude,
            vol.Required(ATTR_LONGITUDE): cv.longitude,
            vol.Required(ATTR_ACCURACY): vol.All(vol.Coerce(float), vol.Range(min=0)),
        },
        func="async_set_tracker_location",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SCANNER_CONNECTED,
        entity_domain=DEVICE_TRACKER_DOMAIN,
        schema={vol.Required(ATTR_CONNECTED): cv.boolean},
        func="async_set_scanner_connected",
    )
