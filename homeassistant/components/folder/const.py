"""Constants for the Folder integration."""

from homeassistant.const import Platform

DOMAIN = "folder"
PLATFORMS = [Platform.SENSOR]

CONF_FOLDER_PATHS = "folder"
CONF_FILTER = "filter"
DEFAULT_FILTER = "*"
