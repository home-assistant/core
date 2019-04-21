"""Component providing default configuration for new users."""
try:
    import av
except ImportError:
    av = None

DOMAIN = 'default_config'
DEPENDENCIES = [
    'automation',
    'cloud',
    'config',
    'conversation',
    'frontend',
    'history',
    'logbook',
    'map',
    'mobile_app',
    'person',
    'script',
    'sun',
    'system_health',
    'updater',
    'zeroconf',
]
# Only automatically set up the stream component when dependency installed
if av is not None:
    DEPENDENCIES.append('stream')


async def async_setup(hass, config):
    """Initialize default configuration."""
    return True
