"""Services for the Python script integration."""

import glob
import logging
import os

from homeassistant.const import CONF_DESCRIPTION, CONF_NAME, SERVICE_RELOAD
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.util.yaml.loader import load_yaml_dict

from .const import DOMAIN, FOLDER
from .helpers import execute_script

_LOGGER = logging.getLogger(__package__)

CONF_FIELDS = "fields"


def discover_scripts(hass: HomeAssistant) -> None:
    """Discover python scripts in folder."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning("Folder %s not found in configuration folder", FOLDER)
        return

    def python_script_service_handler(call: ServiceCall) -> ServiceResponse:
        """Handle python script service calls."""
        return execute_script(hass, call.service, call.data, call.return_response)

    existing = hass.services.services.get(DOMAIN, {}).keys()
    for existing_service in existing:
        if existing_service == SERVICE_RELOAD:
            continue
        hass.services.remove(DOMAIN, existing_service)

    # Load user-provided service descriptions from python_scripts/services.yaml
    services_yaml = os.path.join(path, "services.yaml")
    if os.path.exists(services_yaml):
        services_dict = load_yaml_dict(services_yaml)
    else:
        services_dict = {}

    for fil in glob.iglob(os.path.join(path, "*.py")):
        name = os.path.splitext(os.path.basename(fil))[0]
        # Action names are lowercase, and the built-in reload action must stay
        if name.lower() == SERVICE_RELOAD:
            _LOGGER.warning("Skipping python_script '%s': name is reserved", name)
            continue
        # Cannot be moved: action names come from the script files
        # pylint: disable-next=home-assistant-action-registered-outside-services-module
        hass.services.register(
            DOMAIN,
            name,
            python_script_service_handler,
            supports_response=SupportsResponse.OPTIONAL,
        )

        service_desc = {
            CONF_NAME: services_dict.get(name, {}).get("name", name),
            CONF_DESCRIPTION: services_dict.get(name, {}).get("description", ""),
            CONF_FIELDS: services_dict.get(name, {}).get("fields", {}),
        }
        async_set_service_schema(hass, DOMAIN, name, service_desc)


def _reload_scripts_handler(call: ServiceCall) -> None:
    """Handle reload service calls."""
    discover_scripts(call.hass)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Python script services."""
    hass.services.register(DOMAIN, SERVICE_RELOAD, _reload_scripts_handler)
