"""Component to embed Google Cast."""
from homeassistant import config_entries

from . import home_assistant_cast
from .const import DOMAIN


async def async_setup(hass, config):
    """Set up the Cast component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry: config_entries.ConfigEntry):
    """Set up Cast from a config entry."""
    await home_assistant_cast.async_setup_ha_cast(hass, entry)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True
