"""Provide a mock package component."""
DOMAIN = 'test_package'


async def async_setup(hass, config):
    """Mock a successful setup."""
    return True
