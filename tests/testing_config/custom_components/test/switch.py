"""Stub switch platform for translation tests."""


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Stub setup for translation tests."""
    async_add_entities_callback([])
