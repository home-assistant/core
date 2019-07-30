"""Provide a mock standalone component."""
DOMAIN = 'test_standalone'


async def async_setup(hass, config):
    """Mock a successful setup."""
    return True
