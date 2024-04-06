"""Config flow to configure zone component.

This is no longer in use. This file is around so that existing
config entries will remain to be loaded and then automatically
migrated to the storage collection.
"""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class ZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Stub zone config flow class."""
