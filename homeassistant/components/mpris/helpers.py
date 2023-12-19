"""Helper functions for MPRIS integration."""
from homeassistant.config_entries import ConfigEntry

from .const import CONF_REMOVE_CLONES, CONF_REMOVE_CLONES_DEFAULT_VALUE


def get_remove_clones(entry: ConfigEntry) -> bool:
    """Get value of remove_clones option or its default value."""
    return entry.options.get(CONF_REMOVE_CLONES, CONF_REMOVE_CLONES_DEFAULT_VALUE)
