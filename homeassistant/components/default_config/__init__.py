"""Component providing default configuration for new users."""
try:
    import av
except ImportError:
    av = None

DOMAIN = 'default_config'
# Only automatically set up the stream component when dependency installed
if av is not None:
    DEPENDENCIES.append('stream')


async def async_setup(hass, config):
    """Initialize default configuration."""
    return True
