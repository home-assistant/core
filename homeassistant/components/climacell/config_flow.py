"""Config flow for ClimaCell integration."""
from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class ClimaCellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClimaCell Weather API."""

    VERSION = 1
