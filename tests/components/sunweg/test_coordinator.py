"""Tests for the Sun WEG Coordinator."""

from unittest.mock import MagicMock

from sunweg.api import LoginError, SunWegApiError

from homeassistant.components.sunweg.const import DEFAULT_PLANT_ID, DeviceType
from homeassistant.components.sunweg.coordinator import SunWEGDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_update_listPlants_empty(hass: HomeAssistant) -> None:
    """Test update with empty list of plants."""
    api = MagicMock()
    api.listPlants = MagicMock(return_value=[])
    coordinator = SunWEGDataUpdateCoordinator(hass, api, DEFAULT_PLANT_ID, None)
    await coordinator.async_refresh()
    assert type(coordinator.last_exception) is ConfigEntryError
    assert coordinator.last_exception._message == "No plant found"


async def test_update_plant_none(hass: HomeAssistant) -> None:
    """Test update with plant not found."""
    api = MagicMock()
    api.plant = MagicMock(return_value=None)
    coordinator = SunWEGDataUpdateCoordinator(hass, api, 1, "")
    await coordinator.async_refresh()
    assert type(coordinator.last_exception) is ConfigEntryError
    assert coordinator.last_exception._message == "Plant 1 not found"


async def test_update_auth_error(hass: HomeAssistant) -> None:
    """Test update with authentication error."""
    api = MagicMock()
    api.plant = MagicMock(side_effect=LoginError())
    coordinator = SunWEGDataUpdateCoordinator(hass, api, 1, "")
    await coordinator.async_refresh()
    assert type(coordinator.last_exception) is ConfigEntryAuthFailed


async def test_update_generic_api_error(hass: HomeAssistant) -> None:
    """Test update with generic api error."""
    api = MagicMock()
    api.plant = MagicMock(side_effect=SunWegApiError())
    coordinator = SunWEGDataUpdateCoordinator(hass, api, 1, "")
    await coordinator.async_refresh()
    assert type(coordinator.last_exception) is UpdateFailed


async def test_get_api_value_total(hass: HomeAssistant, plant_fixture) -> None:
    """Test get_api_value with total attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert coordinator.get_api_value("saving", DeviceType.TOTAL) == plant_fixture.saving
    assert (
        coordinator.get_api_value("today_energy", DeviceType.TOTAL)
        == plant_fixture.today_energy
    )
    assert (
        coordinator.get_api_value("today_energy_metric", DeviceType.TOTAL)
        == plant_fixture.today_energy_metric
    )
    assert (
        coordinator.get_api_value("total_power", DeviceType.TOTAL)
        == plant_fixture.total_power
    )
    assert (
        coordinator.get_api_value("total_energy", DeviceType.TOTAL)
        == plant_fixture.total_energy
    )
    assert (
        coordinator.get_api_value("kwh_per_kwp", DeviceType.TOTAL)
        == plant_fixture.kwh_per_kwp
    )
    assert (
        coordinator.get_api_value("last_update", DeviceType.TOTAL)
        == plant_fixture.last_update
    )


async def test_get_api_value_inverter(
    hass: HomeAssistant, plant_fixture, inverter_fixture
) -> None:
    """Test get_api_value with inverter attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert (
        coordinator.get_api_value(
            "today_energy", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.today_energy
    )
    assert (
        coordinator.get_api_value(
            "today_energy_metric", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.today_energy_metric
    )
    assert (
        coordinator.get_api_value(
            "total_energy", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.total_energy
    )
    assert (
        coordinator.get_api_value(
            "total_energy_metric", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.total_energy_metric
    )
    assert (
        coordinator.get_api_value("frequency", DeviceType.INVERTER, inverter_fixture.id)
        == inverter_fixture.frequency
    )
    assert (
        coordinator.get_api_value("power", DeviceType.INVERTER, inverter_fixture.id)
        == inverter_fixture.power
    )
    assert (
        coordinator.get_api_value(
            "power_metric", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.power_metric
    )
    assert (
        coordinator.get_api_value(
            "temperature", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.temperature
    )
    assert (
        coordinator.get_api_value(
            "power_factor", DeviceType.INVERTER, inverter_fixture.id
        )
        == inverter_fixture.power_factor
    )


async def test_get_api_value_wrong_inverter(
    hass: HomeAssistant, plant_fixture, inverter_fixture
) -> None:
    """Test get_api_value with inverter attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert coordinator.get_api_value("today_energy", DeviceType.INVERTER, 0) is None


async def test_get_api_value_phase(
    hass: HomeAssistant, plant_fixture, inverter_fixture, phase_fixture
) -> None:
    """Test get_api_value with phasee attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert (
        coordinator.get_api_value(
            "amperage", DeviceType.PHASE, inverter_fixture.id, phase_fixture.name
        )
        == phase_fixture.amperage
    )
    assert (
        coordinator.get_api_value(
            "voltage", DeviceType.PHASE, inverter_fixture.id, phase_fixture.name
        )
        == phase_fixture.voltage
    )


async def test_get_api_value_wrong_phase(
    hass: HomeAssistant, plant_fixture, inverter_fixture
) -> None:
    """Test get_api_value with phasee attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert (
        coordinator.get_api_value(
            "amperage", DeviceType.PHASE, inverter_fixture.id, "wrong_phase"
        )
        is None
    )


async def test_get_api_value_string(
    hass: HomeAssistant, plant_fixture, inverter_fixture, string_fixture
) -> None:
    """Test get_api_value with phasee attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert (
        coordinator.get_api_value(
            "amperage", DeviceType.STRING, inverter_fixture.id, string_fixture.name
        )
        == string_fixture.amperage
    )
    assert (
        coordinator.get_api_value(
            "voltage", DeviceType.STRING, inverter_fixture.id, string_fixture.name
        )
        == string_fixture.voltage
    )


async def test_get_api_value_wrong_string(
    hass: HomeAssistant, plant_fixture, inverter_fixture
) -> None:
    """Test get_api_value with phasee attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert (
        coordinator.get_api_value(
            "amperage", DeviceType.STRING, inverter_fixture.id, "wrong_string"
        )
        is None
    )
