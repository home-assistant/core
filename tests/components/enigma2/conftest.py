"""Test the Enigma2 config flow."""

from homeassistant.components.enigma2.const import (
    CONF_DEEP_STANDBY,
    CONF_MAC_ADDRESS,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_DEEP_STANDBY,
    DEFAULT_MAC_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SOURCE_BOUQUET,
    DEFAULT_SSL,
    DEFAULT_USE_CHANNEL_ICON,
    DEFAULT_USERNAME,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

TEST_REQUIRED = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
}

TEST_FULL = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_USERNAME: DEFAULT_USERNAME,
    CONF_PASSWORD: DEFAULT_PASSWORD,
}

TEST_IMPORT_FULL = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_USERNAME: DEFAULT_USERNAME,
    CONF_PASSWORD: DEFAULT_PASSWORD,
    CONF_NAME: DEFAULT_NAME,
    CONF_DEEP_STANDBY: DEFAULT_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET: DEFAULT_SOURCE_BOUQUET,
    CONF_MAC_ADDRESS: DEFAULT_MAC_ADDRESS,
    CONF_USE_CHANNEL_ICON: DEFAULT_USE_CHANNEL_ICON,
}

TEST_IMPORT_REQUIRED = {CONF_HOST: "1.1.1.1"}

MAC_ADDRESS = "12:34:56:78:90:ab"


class MockDevice:
    """A mock Enigma2 device."""

    mac_address: str | None = "12:34:56:78:90:ab"
    _base = "http://1.1.1.1"

    async def _call_api(self, url: str) -> dict:
        if url.endswith("/api/about"):
            return {
                "info": {
                    "ifaces": [
                        {
                            "mac": self.mac_address,
                        }
                    ]
                }
            }

    def get_version(self):
        """Return the version."""
        return None

    async def get_about(self) -> dict:
        """Get mock about endpoint."""
        return await self._call_api("/api/about")

    async def close(self):
        """Mock close."""
        pass
