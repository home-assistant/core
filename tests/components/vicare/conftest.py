"""Fixtures for LaMetric integration tests."""
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
from PyViCare.PyViCareUtils import PyViCareInvalidCredentialsError
import pytest

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MODULE

from tests.common import MockConfigEntry


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(name="entity_registry_enabled_by_default", autouse=True)
def entity_registry_enabled_by_default():
    """Test fixture that ensures all entities are enabled in the registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ) as mock_entity_registry_enabled_by_default:
        yield mock_entity_registry_enabled_by_default


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
        print("Read: ", property_name, value)
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


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=ENTRY_CONFIG,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the ViCare integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def mock_vicare_gas_boiler() -> Generator[MagicMock, None, None]:
    """Return a mocked ViCare API representing a single gas boiler device."""
    fixtures = ["fixtures/Vitodens300W.json"]
    with patch(
        f"{MODULE}.vicare_login",
        return_value=MockPyViCare(fixtures),
    ) as vicare_mock:
        vicare = vicare_mock.return_value
        yield vicare


@pytest.fixture
async def mock_vicare_2_gas_boilers() -> Generator[MagicMock, None, None]:
    """Return a mocked ViCare API representing two gas boiler devices."""
    fixtures = ["fixtures/Vitodens300W.json", "fixtures/Vitodens300W.json"]
    with patch(
        f"{MODULE}.vicare_login",
        return_value=MockPyViCare(fixtures),
    ) as vicare_mock:
        vicare = vicare_mock.return_value
        yield vicare


@pytest.fixture
async def mock_vicare_login_config_flow():
    """Return a mocked ViCare API representing a gas boiler device."""
    fixtures = ["fixtures/Vitodens300W.json", "fixtures/Vitodens300W.json"]
    with patch(
        f"{MODULE}.config_flow.vicare_login", return_value=MockPyViCare(fixtures)
    ) as mock_vicare_login_config_flow:
        yield mock_vicare_login_config_flow


@pytest.fixture
async def mock_vicare_login_invalid_credentials_config_flow():
    """Throw PyViCareInvalidCredentialsError when logging in."""
    with patch(
        f"{MODULE}.config_flow.vicare_login",
        side_effect=PyViCareInvalidCredentialsError(),
    ) as mock_vicare_login_config_flow:
        yield mock_vicare_login_config_flow


@pytest.fixture
async def mock_setup_entry() -> bool:
    """Return a mocked ViCare API representing a gas boiler device."""
    with patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry
