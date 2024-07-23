"""Config flow."""

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant


class MockConfigFlow(
    ConfigFlow, domain="test_package_raises_cancelled_error_config_entry"
):
    """Mock config flow."""


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    return True
