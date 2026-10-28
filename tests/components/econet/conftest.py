"""Fixtures for EcoNet tests."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, patch

from pyeconet.api import EcoNetApiInterface
from pyeconet.equipment import Equipment, EquipmentType
from pyeconet.equipment.thermostat import Thermostat
from pyeconet.equipment.water_heater import WaterHeater
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)

from homeassistant.components.econet.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide an EcoNet config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
    )


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Mock the EcoNet API without connecting to the cloud."""
    api = MagicMock(spec=EcoNetApiInterface)
    with patch(
        "homeassistant.components.econet.EcoNetApiInterface.login", return_value=api
    ):
        yield api


@pytest.fixture
def equipment_data(request: pytest.FixtureRequest) -> dict:
    """Provide API data for the selected equipment."""
    return load_json_object_fixture(
        f"{getattr(request, 'param', 'water_heater')}.json", DOMAIN
    )


@pytest.fixture
def mock_equipment(equipment_data: dict, mock_api: MagicMock) -> Equipment:
    """Provide equipment with the library's real properties and update callbacks."""
    equipment_class = {"WH": WaterHeater, "HVAC": Thermostat}[
        equipment_data["device_type"]
    ]
    return equipment_class(equipment_data, mock_api)


@pytest.fixture
def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    mock_equipment: Equipment,
    platform: Platform,
) -> Generator[Callable[[], Awaitable[None]]]:
    """Set up the requested platform after any registry entries are prepared."""
    mock_config_entry.add_to_hass(hass)
    mock_api.get_equipment_by_type.return_value = {
        EquipmentType.WATER_HEATER: [],
        EquipmentType.THERMOSTAT: [],
    }
    mock_api.get_equipment_by_type.return_value[mock_equipment.type].append(
        mock_equipment
    )

    async def setup() -> None:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch("homeassistant.components.econet.PLATFORMS", [platform]):
        yield setup


@pytest.fixture
async def energy_usage(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_api: MagicMock,
    mock_equipment: Equipment,
) -> None:
    """Populate water heater energy usage from a mocked API response."""
    response = await async_load_json_object_fixture(hass, "energy_usage.json", DOMAIN)
    response["results"]["energy_usage"]["message"] = f"Energy usage in {request.param}"
    mock_api.get_dynamic_action.return_value = response
    assert isinstance(mock_equipment, WaterHeater)
    await mock_equipment.get_energy_usage()
