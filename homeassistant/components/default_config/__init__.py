"""Component providing default configuration for new users."""

DOMAIN = 'default_config'
DEPENDENCIES = (
    'automation',
    'cloud',
    'config',
    'conversation',
    'discovery',
    'frontend',
    'history',
    'logbook',
    'map',
    'person',
    'script',
    'sun',
    'system_health',
    'updater',
)


async def async_setup(hass, config):
    """Initialize default configuration."""
    return True
