"""Constants for Lovelace."""
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "lovelace"
EVENT_LOVELACE_UPDATED = "lovelace_updated"

MODE_YAML = "yaml"
MODE_STORAGE = "storage"

LOVELACE_CONFIG_FILE = "ui-lovelace.yaml"
CONF_RESOURCES = "resources"
CONF_URL_PATH = "url_path"


class ConfigNotFound(HomeAssistantError):
    """When no config available."""
