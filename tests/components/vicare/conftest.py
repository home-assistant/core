"""Fixtures for ViCare integration tests."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch

import pytest
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareService import ViCareDeviceAccessor, readFeature

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MODULE

from tests.common import MockConfigEntry, load_json_object_fixture


@dataclass
class Fixture:
    """Fixture representation with the assigned roles and dummy data location."""

    roles: set[str]
    data_file: str


class MockPyViCare:
    """Mocked PyVicare class based on a json dump."""

    def __init__(self, fixtures: list[Fixture]) -> None:
        """Init a single device from json dump."""
        self.devices = []
        for idx, fixture in enumerate(fixtures):
            self.devices.append(
                PyViCareDeviceConfig(
                    MockViCareService(
                        f"installation{idx}", f"gateway{idx}", f"device{idx}", fixture
                    ),
                    f"deviceId{idx}",
                    f"model{idx}",
                    f"online{idx}",
                )
            )


class MockViCareService:
    """PyVicareService mock using a json dump."""

    def __init__(
        self, installation_id: str, gateway_id: str, device_id: str, fixture: Fixture
    ) -> None:
        """Initialize the mock from a json dump."""
        self._test_data = load_json_object_fixture(fixture.data_file)
        self.fetch_all_features = Mock(return_value=self._test_data)
        self.roles = fixture.roles
        self.accessor = ViCareDeviceAccessor(installation_id, gateway_id, device_id)

    def hasRoles(self, requested_roles: list[str]) -> bool:
        """Return true if requested roles are assigned."""
        return requested_roles and set(requested_roles).issubset(self.roles)

    def getProperty(self, property_name: str):
        """Read a property from json dump."""
        return readFeature(self._test_data["data"], property_name)


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
) -> AsyncGenerator[MockConfigEntry, None]:
    """Return a mocked ViCare API representing a single gas boiler device."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
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
