"""The Hisense AEH-W4A1 integration."""
import voluptuous as vol

from .const import DOMAIN


CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}})


async def async_setup(hass, config):
    """Set up the Hisense AEH-W4A1 integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for NEW_NAME."""
    # TODO forward the entry for each platform that you want to set up.
    # hass.async_create_task(
    #     hass.config_entries.async_forward_entry_setup(entry, "media_player")
    # )

    return True
