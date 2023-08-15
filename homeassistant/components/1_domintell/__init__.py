import logging


async def async_setup(hass, config):
    """Set up the Domintell integration."""

    # Here you would typically initiate a connection to your devices or systems.
    # For demonstration purposes, let's just log some text.

    _LOGGER = logging.getLogger(__name__)
    _LOGGER.info("Domintell integration is setting up...")

    # Let's also pretend we discovered one device and want to add it.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config, "switch")
    )

    return True
