"""Support for IHC devices."""
import logging

from ihcsdk.ihccontroller import IHCController
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .auto_setup import autosetup_ihc_products
from .const import (
    CONF_AUTOSETUP,
    CONF_INFO,
    DOMAIN,
    IHC_CONTROLLER,
    IHC_CONTROLLER_INDEX,
)
from .manual_setup import IHC_SCHEMA, get_manual_configuration
from .service_functions import setup_service_functions

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [IHC_SCHEMA]))}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IHC integration."""
    conf = config[DOMAIN]
    for index, controller_conf in enumerate(conf):
        if not ihc_setup(hass, config, controller_conf, index):
            return False
    return True


def ihc_setup(
    hass: HomeAssistant,
    config: ConfigType,
    controller_conf: ConfigType,
    controller_index: int,
) -> bool:
    """Set up the IHC integration."""
    url = controller_conf[CONF_URL]
    username = controller_conf[CONF_USERNAME]
    password = controller_conf[CONF_PASSWORD]

    ihc_controller = IHCController(url, username, password)
    if not ihc_controller.authenticate():
        _LOGGER.error("Unable to authenticate on IHC controller")
        return False
    controller_id: str = ihc_controller.client.get_system_info()["serial_number"]
    # Store controller configuration
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][controller_id] = {
        IHC_CONTROLLER: ihc_controller,
        CONF_INFO: controller_conf[CONF_INFO],
        IHC_CONTROLLER_INDEX: controller_index,
    }
    if controller_conf[CONF_AUTOSETUP] and not autosetup_ihc_products(
        hass, config, ihc_controller, controller_id
    ):
        return False
    get_manual_configuration(hass, config, controller_conf, controller_id)
    # We only want to register the service functions once for the first controller
    if controller_index == 0:
        setup_service_functions(hass)
    return True
