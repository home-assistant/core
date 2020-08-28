"""The 1-Wire component."""
import voluptuous as vol

from .const import DOMAIN
from .onewireproxy import OneWireProxy

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({}, extra=vol.ALLOW_EXTRA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Old way of setting up 1-Wire integrations."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a 1-Wire proxy for a config entry."""
    hass.data.setdefault(DOMAIN, {})

    owproxy = OneWireProxy(hass, config_entry.data)
    if not owproxy.setup():
        return False

    hass.data[DOMAIN][config_entry.entry_id] = owproxy
    owproxy.load_entities(config_entry)

    return True
