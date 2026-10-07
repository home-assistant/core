"""Services for the Local file integration."""

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_UPDATE_FILE_PATH


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Local file integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_FILE_PATH,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(CONF_FILE_PATH): cv.string},
        func="update_file_path",
    )
