"""Migrate old manual configuration from configuration.yaml."""
import logging
import os.path

from ihcsdk.ihccontroller import IHCController
import yaml

from homeassistant.config import load_yaml_config_file
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, IHC_PLATFORMS, MANUAL_SETUP_YAML

_LOGGER = logging.getLogger(__name__)


def migrate_configuration(hass: HomeAssistant):
    """Migrate the old manual configuration from configuration.yaml to ihc_manual_setup.yaml."""
    yaml_manual_setup_path = hass.config.path(MANUAL_SETUP_YAML)
    if os.path.exists(yaml_manual_setup_path):
        _LOGGER.warning(
            "The %s already exist. Migrating old configuration skipped",
            yaml_manual_setup_path,
        )
        return
    # We will load the configuration.yaml file to get the 'ihc' section
    # We do not want to use the config passed to setup because we do not
    # want the default values added by the config schema
    _LOGGER.debug("Migrating old IHC configuration")
    yaml_path = hass.config.path("configuration.yaml")
    conf = load_yaml_config_file(yaml_path)[DOMAIN]
    newconf: dict = {DOMAIN: []}
    has_manual_config = False
    if not isinstance(conf, list):
        conf = [conf]
    for controllerconf in conf:
        serial = get_controller_serial(controllerconf)
        newcontrollerconf = {"controller": serial}
        for component in IHC_PLATFORMS:
            if component in controllerconf and len(controllerconf[component]) > 0:
                has_manual_config = True
                newcontrollerconf[component] = []
                i = -1
                for j in controllerconf[component]:
                    newcontrollerconf[component].append({})
                    i = i + 1
                    for key in j:
                        value = j[key]
                        newcontrollerconf[component][i][key] = value
        newconf[DOMAIN].append(newcontrollerconf)

    if not has_manual_config:
        _LOGGER.debug("No manual configuration in old IHC configuration")
        return
    with open(yaml_manual_setup_path, "w", encoding="utf8") as file:
        yaml.dump(newconf, file, default_flow_style=False, sort_keys=False)
    _LOGGER.warning(
        "Your old ihc configuration in configuration.yaml "
        "file has been copied to the file %s"
        "You can now delete the ihc section in configuration.yaml. "
        "Restart Home Assistant and add the IHC controller through the UI. "
        "See https://www.home-assistant.io/integrations/ihc/"
        " for more information",
        yaml_manual_setup_path,
    )
    return


def get_controller_serial(controllerconf):
    """Get the controller serial number. We use this as a controller id."""
    url = controllerconf[CONF_URL]
    username = controllerconf[CONF_USERNAME]
    password = controllerconf[CONF_PASSWORD]
    controller = IHCController(url, username, password)
    try:
        if not IHCController.is_ihc_controller(url):
            raise HomeAssistantError("IHC controller not available at specified url")
        if not controller.authenticate():
            raise HomeAssistantError("unable to authencitate on IHC controller")
        system_info = controller.client.get_system_info()
        _LOGGER.debug("IHC system info %s", system_info)
        serial = system_info["serial_number"]
    finally:
        controller.disconnect()
    return serial
