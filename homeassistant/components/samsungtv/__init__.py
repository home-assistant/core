"""The Samsung TV integration."""
import voluptuous as vol
from wakeonlan import BROADCAST_IP

from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
)
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DEFAULT_TIMEOUT, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_PORT): cv.port,
                        vol.Optional(CONF_MAC): cv.string,
                        vol.Optional(
                            CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                        ): cv.positive_int,
                        vol.Optional(
                            CONF_BROADCAST_ADDRESS, default=BROADCAST_IP
                        ): cv.string,
                    }
                )
            ]
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the Samsung TV platform."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True
