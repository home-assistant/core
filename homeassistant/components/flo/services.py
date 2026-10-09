"""Services for the Flo integration."""

from aioflo.location import SLEEP_MINUTE_OPTIONS, SYSTEM_MODE_HOME, SYSTEM_REVERT_MODES
import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

ATTR_REVERT_TO_MODE = "revert_to_mode"
ATTR_SLEEP_MINUTES = "sleep_minutes"
SERVICE_SET_SLEEP_MODE = "set_sleep_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_HOME_MODE = "set_home_mode"
SERVICE_RUN_HEALTH_TEST = "run_health_test"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Flo integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_AWAY_MODE,
        entity_domain=SWITCH_DOMAIN,
        schema=None,
        func="async_set_mode_away",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HOME_MODE,
        entity_domain=SWITCH_DOMAIN,
        schema=None,
        func="async_set_mode_home",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RUN_HEALTH_TEST,
        entity_domain=SWITCH_DOMAIN,
        schema=None,
        func="async_run_health_test",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SLEEP_MODE,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(ATTR_SLEEP_MINUTES, default=120): probatio.All(
                probatio.Coerce(int), probatio.In(SLEEP_MINUTE_OPTIONS)
            ),
            probatio.Required(
                ATTR_REVERT_TO_MODE, default=SYSTEM_MODE_HOME
            ): probatio.In(SYSTEM_REVERT_MODES),
        },
        func="async_set_mode_sleep",
    )
