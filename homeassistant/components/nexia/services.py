"""Services for the Nexia/American Standard/Trane integration."""

from nexia.const import HOLD_PERMANENT, HOLD_RESUME_SCHEDULE
import probatio

from homeassistant.components.climate import (
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_AIRCLEANER_MODE, ATTR_RUN_MODE, DOMAIN

SERVICE_SET_AIRCLEANER_MODE = "set_aircleaner_mode"
SERVICE_SET_HUMIDIFY_SETPOINT = "set_humidify_setpoint"
SERVICE_SET_DEHUMIDIFY_SETPOINT = "set_dehumidify_setpoint"
SERVICE_SET_HVAC_RUN_MODE = "set_hvac_run_mode"
SET_AIRCLEANER_SCHEMA: VolDictType = {
    probatio.Required(ATTR_AIRCLEANER_MODE): cv.string,
}
SET_HUMIDIFY_SCHEMA: VolDictType = {
    probatio.Required(ATTR_HUMIDITY): probatio.All(
        probatio.Coerce(int), probatio.Range(min=10, max=45)
    ),
}
SET_DEHUMIDIFY_SCHEMA: VolDictType = {
    probatio.Required(ATTR_HUMIDITY): probatio.All(
        probatio.Coerce(int), probatio.Range(min=35, max=65)
    ),
}
SET_HVAC_RUN_MODE_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_RUN_MODE, ATTR_HVAC_MODE),
    cv.make_entity_service_schema(
        {
            probatio.Optional(ATTR_RUN_MODE): probatio.In(
                [HOLD_PERMANENT, HOLD_RESUME_SCHEDULE]
            ),
            probatio.Optional(ATTR_HVAC_MODE): probatio.In(
                [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
            ),
        }
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Nexia/American Standard/Trane integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HUMIDIFY_SETPOINT,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_HUMIDIFY_SCHEMA,
        func=f"async_{SERVICE_SET_HUMIDIFY_SETPOINT}",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DEHUMIDIFY_SETPOINT,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_DEHUMIDIFY_SCHEMA,
        func=f"async_{SERVICE_SET_DEHUMIDIFY_SETPOINT}",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_AIRCLEANER_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_AIRCLEANER_SCHEMA,
        func=f"async_{SERVICE_SET_AIRCLEANER_MODE}",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HVAC_RUN_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_HVAC_RUN_MODE_SCHEMA,
        func=f"async_{SERVICE_SET_HVAC_RUN_MODE}",
    )
