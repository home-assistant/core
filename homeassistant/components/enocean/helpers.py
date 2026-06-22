"""Helpers for the EnOcean integration."""

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .types import EnOceanConfigEntryData, EnOceanConfigStore


@callback
def get_enocean(hass: HomeAssistant) -> EnOceanConfigStore:
    """Return EnOceanConfigStore instance."""
    # NOTE: This assumes only one EnOcean connection can exist.
    enocean_config_entry_data: EnOceanConfigEntryData = next(
        iter(hass.data[DOMAIN].values())
    )
    return enocean_config_entry_data.config_store
