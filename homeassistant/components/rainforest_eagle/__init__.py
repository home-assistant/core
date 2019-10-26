"""The Rainforest Eagle integration."""
import voluptuous as vol

CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Rainforest Eagle from YAML configuration."""
    # Not supported, for backwatds compatibility use platform setup instead
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Rainforest Eagle."""
    # ip_addr, cloud_id, install_code

    # Only one type, so create that
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True
