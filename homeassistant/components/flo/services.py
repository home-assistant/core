"""Services for the Flow by Moen integration."""
from aioflo.api import API
from aioflo.location import SLEEP_MINUTE_OPTIONS, SYSTEM_MODE_HOME, SYSTEM_REVERT_MODES
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import CLIENT, DOMAIN as FLO_DOMAIN

ATTR_LOCATION_ID = "location_id"
ATTR_DEVICE_ID = "device_id"
ATTR_REVERT_TO_MODE = "revert_to_mode"
ATTR_SLEEP_MINUTES = "sleep_minutes"

DEVICE_ID_SERVICE = "device_id_service"
LOCATION_ID_SERVICE = "location_id_service"

SERVICE_SET_SLEEP_MODE = "set_sleep_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_HOME_MODE = "set_home_mode"
SERVICE_RUN_HEALTH_TEST = "run_health_test"

SERVICE_SCHEMAS = {
    DEVICE_ID_SERVICE: vol.Schema(
        {vol.Required(ATTR_DEVICE_ID, default=None): cv.string}
    ),
    LOCATION_ID_SERVICE: vol.Schema(
        {vol.Required(ATTR_LOCATION_ID, default=None): cv.string}
    ),
    SERVICE_SET_SLEEP_MODE: vol.Schema(
        {
            vol.Required(ATTR_LOCATION_ID, default=None): cv.string,
            vol.Required(ATTR_SLEEP_MINUTES, default=120): vol.In(SLEEP_MINUTE_OPTIONS),
            vol.Required(ATTR_REVERT_TO_MODE, default=SYSTEM_MODE_HOME): vol.In(
                SYSTEM_REVERT_MODES
            ),
        }
    ),
}


@callback
def async_load_services(hass):
    """Load the services exposed by the Flo component."""

    async def async_set_mode_home(hass: HomeAssistantType, service):
        """Set the Flo location to home mode."""
        location_id: str = service.data.get(ATTR_LOCATION_ID)
        api: API = hass.data[FLO_DOMAIN][CLIENT]
        await api.location.set_mode_home(location_id)

    hass.helpers.service.async_register_admin_service(
        FLO_DOMAIN,
        SERVICE_SET_HOME_MODE,
        async_set_mode_home,
        schema=SERVICE_SCHEMAS[LOCATION_ID_SERVICE],
    )

    async def async_set_mode_away(hass: HomeAssistantType, service):
        """Set the Flo location to away mode."""
        location_id: str = service.data.get(ATTR_LOCATION_ID)
        api: API = hass.data[FLO_DOMAIN][CLIENT]
        await api.location.set_mode_away(location_id)

    hass.helpers.service.async_register_admin_service(
        FLO_DOMAIN,
        SERVICE_SET_AWAY_MODE,
        async_set_mode_home,
        schema=SERVICE_SCHEMAS[LOCATION_ID_SERVICE],
    )

    async def async_set_mode_sleep(hass: HomeAssistantType, service):
        """Set the Flo location to sleep mode."""
        location_id: str = service.data.get(ATTR_LOCATION_ID)
        sleep_minutes: int = service.data.get(ATTR_SLEEP_MINUTES)
        revert_to_mode: str = service.data.get(ATTR_REVERT_TO_MODE)
        api: API = hass.data[FLO_DOMAIN][CLIENT]
        await api.location.set_mode_sleep(location_id, sleep_minutes, revert_to_mode)

    hass.helpers.service.async_register_admin_service(
        FLO_DOMAIN,
        SERVICE_SET_SLEEP_MODE,
        async_set_mode_home,
        schema=SERVICE_SCHEMAS[SERVICE_SET_SLEEP_MODE],
    )

    async def async_run_health_test(hass: HomeAssistantType, service):
        """Run a Flo device health test."""
        device_id: str = service.data.get(ATTR_DEVICE_ID)
        api: API = hass.data[FLO_DOMAIN][CLIENT]
        await api.device.run_health_test(device_id)

    hass.helpers.service.async_register_admin_service(
        FLO_DOMAIN,
        SERVICE_RUN_HEALTH_TEST,
        async_set_mode_home,
        schema=SERVICE_SCHEMAS[DEVICE_ID_SERVICE],
    )


@callback
def async_unload_services(hass):
    """Unload the Flo services."""
    hass.services.async_remove(FLO_DOMAIN, SERVICE_SET_SLEEP_MODE)
    hass.services.async_remove(FLO_DOMAIN, SERVICE_SET_AWAY_MODE)
    hass.services.async_remove(FLO_DOMAIN, SERVICE_SET_HOME_MODE)
    hass.services.async_remove(FLO_DOMAIN, SERVICE_RUN_HEALTH_TEST)
