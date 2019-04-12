"""Component providing default configuration for new users."""
try:
    import av
except ImportError:
    av = None

DOMAIN = 'default_config'


async def async_setup(hass, config):
    """Initialize default configuration."""
    return True
