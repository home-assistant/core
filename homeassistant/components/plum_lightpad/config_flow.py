"""Config flow for Plum Lightpad."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class PlumLightpadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Plum Lightpad integration."""

    VERSION = 1
