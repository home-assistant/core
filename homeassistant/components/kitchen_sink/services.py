"""Services for the Everything but the Kitchen Sink integration."""

from enum import StrEnum

import probatio

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class KitchenSinkService(StrEnum):
    """Store keys for Everything but the Kitchen Sink services."""

    TEST_SERVICE_1 = "test_service_1"
    SET_TRACKER_LOCATION = "set_tracker_location"
    SET_SCANNER_CONNECTED = "set_scanner_connected"


class KitchenSinkServiceArgument(StrEnum):
    """Store keys for Everything but the Kitchen Sink service arguments."""

    FIELD_1 = "field_1"
    FIELD_2 = "field_2"
    FIELD_3 = "field_3"
    FIELD_4 = "field_4"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    ACCURACY = "accuracy"
    CONNECTED = "connected"


SCHEMA_SERVICE_TEST_SERVICE_1 = probatio.Schema(
    {
        probatio.Required(KitchenSinkServiceArgument.FIELD_1): probatio.Coerce(int),
        probatio.Required(KitchenSinkServiceArgument.FIELD_2): probatio.In(
            ["off", "auto", "cool"]
        ),
        probatio.Optional(KitchenSinkServiceArgument.FIELD_3): probatio.Coerce(int),
        probatio.Optional(KitchenSinkServiceArgument.FIELD_4): probatio.In(
            ["forward", "reverse"]
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Kitchen Sink integration."""

    @callback
    def service_handler(call: ServiceCall) -> ServiceResponse:
        """Do nothing."""
        return None

    hass.services.async_register(
        DOMAIN,
        KitchenSinkService.TEST_SERVICE_1,
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
        KitchenSinkService.SET_TRACKER_LOCATION,
        entity_domain=DEVICE_TRACKER_DOMAIN,
        schema={
            probatio.Required(KitchenSinkServiceArgument.LATITUDE): cv.latitude,
            probatio.Required(KitchenSinkServiceArgument.LONGITUDE): cv.longitude,
            probatio.Required(KitchenSinkServiceArgument.ACCURACY): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0)
            ),
        },
        func="async_set_tracker_location",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        KitchenSinkService.SET_SCANNER_CONNECTED,
        entity_domain=DEVICE_TRACKER_DOMAIN,
        schema={probatio.Required(KitchenSinkServiceArgument.CONNECTED): cv.boolean},
        func="async_set_scanner_connected",
    )
