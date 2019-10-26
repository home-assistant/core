"""The Rainforest Eagle integration."""
import voluptuous as vol

CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Rainforest Eagle integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for NEW_NAME."""
    # ip_addr, cloud_id, install_code

    # Only one type of device so far
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True
