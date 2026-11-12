"""Constants for the shell_command integration."""

import probatio

from homeassistant.helpers import config_validation as cv

DOMAIN = "shell_command"

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(cv.string)}, extra=probatio.ALLOW_EXTRA
)
