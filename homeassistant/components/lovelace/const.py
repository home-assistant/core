"""Constants for Lovelace."""
import voluptuous as vol

from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

DOMAIN = "lovelace"
EVENT_LOVELACE_UPDATED = "lovelace_updated"

MODE_YAML = "yaml"
MODE_STORAGE = "storage"

LOVELACE_CONFIG_FILE = "ui-lovelace.yaml"
CONF_RESOURCES = "resources"
CONF_URL_PATH = "url_path"
CONF_RESOURCE_TYPE_WS = "res_type"

RESOURCE_TYPES = ["js", "css", "module", "html"]

RESOURCE_FIELDS = {
    CONF_TYPE: vol.In(RESOURCE_TYPES),
    CONF_URL: cv.string,
}

RESOURCE_SCHEMA = vol.Schema(RESOURCE_FIELDS)

RESOURCE_CREATE_FIELDS = {
    vol.Required(CONF_RESOURCE_TYPE_WS): vol.In(RESOURCE_TYPES),
    vol.Required(CONF_URL): cv.string,
}

RESOURCE_UPDATE_FIELDS = {
    vol.Optional(CONF_RESOURCE_TYPE_WS): vol.In(RESOURCE_TYPES),
    vol.Optional(CONF_URL): cv.string,
}


class ConfigNotFound(HomeAssistantError):
    """When no config available."""
