"""Fixtures for ViCare integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareService import (
    ViCareDeviceAccessor,
    buildSetPropertyUrl,
    readFeature,
)
import pytest

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MODULE

from tests.common import MockConfigEntry, load_json_object_fixture


class MockPyViCare:
    """Mocked PyVicare class based on a json dump."""

    def __init__(self, fixtures: list[str]) -> None:
        """Init a single device from json dump."""
        self.devices = []
        for idx, fixture in enumerate(fixtures):
            self.devices.append(
                PyViCareDeviceConfig(
                    ViCareServiceMock(
                        fixture,
                        f"installationId{idx}",
                        f"serial{idx}",
                        f"deviceId{idx}",
                        ["type:boiler"],
                    ),
                    f"deviceId{idx}",
                    f"model{idx}",
                    f"online{idx}",
                )
            )

    def setCacheDuration(self, cache_duration: int):
        """Set cache duration to limit # of requests."""
        self.cacheDuration = int(cache_duration)

    def initWithCredentials(
        self, username: str, password: str, client_id: str, token_file: str
    ) -> None:
        """Stub oauth login."""


class ViCareServiceMock:
    """PyVicareService mock using a json dump."""

    def __init__(
        self, fixture: str, inst_id: int, serial: str, device_id: str, roles: list[str]
    ):
        """Initialize the mock from a json dump."""
        self.__testData = load_json_object_fixture(fixture)

        self.accessor = ViCareDeviceAccessor(inst_id, serial, device_id)
        self.setPropertyData = []
        self.roles = roles

    def getProperty(self, property_name: str):
        """Read a property from a json dump."""
        entities = self.__testData["data"]
        value = readFeature(entities, property_name)
        return value

    def setProperty(self, property_name: str, action: str, data: str):
        """Set a property to its internal data structure."""
        self.setPropertyData.append(
            {
                "url": buildSetPropertyUrl(self.accessor, property_name, action),
                "property_name": property_name,
                "action": action,
                "data": data,
            }
        )

    def hasRoles(self, requested_roles: list[str]) -> bool:
        """Return true if requested roles are supported."""
        return len(requested_roles) > 0 and set(requested_roles).issubset(
            set(self.roles)
        )

    def fetch_all_features(self) -> str:
        """Return the full json dump."""
        return self.__testData


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        entry_id="1234",
        data=ENTRY_CONFIG,
    )


@pytest.fixture
async def mock_vicare_gas_boiler(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> Generator[MagicMock, None, None]:
    """Return a mocked ViCare API representing a single gas boiler device."""
    fixtures = ["vicare/Vitodens300W.json"]
    with patch(
        f"{MODULE}.vicare_login",
        return_value=MockPyViCare(fixtures),
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        yield mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry
