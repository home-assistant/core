"""The vizio component."""

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)


def validate_auth(config: ConfigType) -> ConfigType:
    """Validate presence of CONF_ACCESS_TOKEN when CONF_DEVICE_CLASS=tv."""

    token = config.get(CONF_ACCESS_TOKEN)
    if config[CONF_DEVICE_CLASS] == "tv" and not token:
        raise vol.Invalid(
            f"When '{CONF_DEVICE_CLASS}' is 'tv' then '{CONF_ACCESS_TOKEN}' is required.",
            path=[CONF_ACCESS_TOKEN],
        )
    return config


VIZIO_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.All(
        cv.string, vol.Lower, vol.In(["tv", "soundbar"])
    ),
    vol.Optional(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=10)
    ),
}

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: [vol.All(vol.Schema(VIZIO_SCHEMA), validate_auth)]}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Platform setup, run import config flow for each entry in config."""

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Load the saved entities."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(entry, "media_player")
    )

    return True
