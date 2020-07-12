"""Helper functions for SmartTub integration."""

from homeassistant.config_entries import SOURCE_IMPORT

from .const import DOMAIN


def create_config_flow(hass, data={}):
    """Create a new config flow to set up the SmartTub integration."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data,
        )
    )
