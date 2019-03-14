"""Component providing default configuration for new users."""

DOMAIN = 'default_config'
DEPENDENCIES = (
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
)


async def async_setup(hass, config):
    """Initialize default configuration."""
    return True
