"""Schemas for the shell_command integration."""

import probatio

from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(cv.string)}, extra=probatio.ALLOW_EXTRA
)
