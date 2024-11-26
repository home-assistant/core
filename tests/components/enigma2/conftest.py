"""Test the Enigma2 config flow."""

from openwebif.api import OpenWebIfServiceEvent, OpenWebIfStatus

from homeassistant.components.enigma2.const import (
    CONF_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_DEEP_STANDBY,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MAC_ADDRESS = "12:34:56:78:90:ab"

TEST_REQUIRED = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

TEST_FULL = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

EXPECTED_OPTIONS = {
    CONF_DEEP_STANDBY: DEFAULT_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET: "Favourites",
    CONF_USE_CHANNEL_ICON: False,
}


class MockDevice:
    """A mock Enigma2 device."""

    mac_address: str | None = "12:34:56:78:90:ab"
    _base = "http://1.1.1.1"

    def __init__(self) -> None:
        """Initialize the mock Enigma2 device."""
        self.status = OpenWebIfStatus(currservice=OpenWebIfServiceEvent())

    async def _call_api(self, url: str) -> dict | None:
        if url.endswith("/api/about"):
            return {
                "info": {
                    "ifaces": [
                        {
                            "mac": self.mac_address,
                        }
                    ],
                    "model": "Mock Enigma2",
                    "brand": "Enigma2",
                }
            }
        return None

    def get_version(self) -> str | None:
        """Return the version."""
        return None

    async def get_about(self) -> dict:
        """Get mock about endpoint."""
        return await self._call_api("/api/about")

    async def get_all_bouquets(self) -> dict:
        """Get all bouquets."""
        return {
            "bouquets": [
                [
                    '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet',
                    "Favourites (TV)",
                ]
            ]
        }

    async def update(self) -> None:
        """Mock update."""

    async def close(self):
        """Mock close."""
