"""Test helpers for decora_wifi."""

from homeassistant.components.decora_wifi.common import DecoraWifiPlatform
from homeassistant.core import HomeAssistant


class MockDecoraWifiPlatform(DecoraWifiPlatform):
    """Class to simulate decora_wifi platform sessions and related methods for unit testing."""

    def __init__(self, email: str, password: str) -> None:
        """Iniialize session holder."""
        self._email = email
        self._password = password

    def __del__(self):
        """Clean up the session on object deletion."""
        pass

    @staticmethod
    async def async_setup_decora_wifi(hass: HomeAssistant, email: str, password: str):
        """Set up a mock decora wifi session."""

        def setupplatform():
            return MockDecoraWifiPlatform(email, password)

        return await hass.async_add_executor_job(setupplatform)
