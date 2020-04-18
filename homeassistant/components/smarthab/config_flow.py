"""SmartHab configuration flow."""
from homeassistant import config_entries

from . import DOMAIN


class SmartHabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SmartHab config flow."""
