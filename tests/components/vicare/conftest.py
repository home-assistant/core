"""Fixtures for ViCare integration tests."""
from __future__ import annotations

from collections.abc import Generator
import json
import os
from unittest.mock import MagicMock, patch

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

from tests.common import MockConfigEntry


def readJson(fileName):
    """Read filte to json."""
    test_filename = os.path.join(os.path.dirname(__file__), fileName)
    with open(test_filename, mode="rb") as json_file:
        return json.load(json_file)


class MockPyViCare:
    """Mocked PyVicare class based on a json dump."""

    def setCacheDuration(self, cache_duration):
        """Set cache duration to limit # of requests."""
        self.cacheDuration = int(cache_duration)

    def __init__(self, fixtures) -> None:
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

    def initWithCredentials(
        self, username: str, password: str, client_id: str, token_file: str
    ):
        """Stub oauth login."""
        None


class ViCareServiceMock:
    """PyVicareService mock using a json dump."""

    def __init__(self, fixture, inst_id, serial, device_id, roles):
        """Initialize the mock from a json dump."""
        testData = readJson(fixture)
        self.testData = testData

        self.accessor = ViCareDeviceAccessor(inst_id, serial, device_id)
        self.setPropertyData = []
        self.roles = roles

    def getProperty(self, property_name):
        """Read a property from a json dump."""
        entities = self.testData["data"]
        value = readFeature(entities, property_name)
        return value

    def setProperty(self, property_name, action, data):
        """Set a property to its internal data structure."""
        self.setPropertyData.append(
            {
                "url": buildSetPropertyUrl(self.accessor, property_name, action),
                "property_name": property_name,
                "action": action,
                "data": data,
            }
        )

    def hasRoles(self, requested_roles) -> bool:
        """Return true if requested roles are supported."""
        return len(requested_roles) > 0 and set(requested_roles).issubset(
            set(self.roles)
        )

    def fetch_all_features(self) -> str:
        """Return the full json dump."""
        return self.testData


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=ENTRY_CONFIG,
    )


@pytest.fixture
async def mock_vicare_gas_boiler(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> Generator[MagicMock, None, None]:
    """Return a mocked ViCare API representing a single gas boiler device."""
    fixtures = ["fixtures/Vitodens300W.json"]
    with patch(
        f"{MODULE}.vicare_login",
        return_value=MockPyViCare(fixtures),
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        yield mock_config_entry


@pytest.fixture
async def mock_setup_entry() -> bool:
    """Return a mocked ViCare API representing a gas boiler device."""
    with patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry
