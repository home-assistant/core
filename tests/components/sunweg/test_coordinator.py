"""Tests for the Sun WEG Coordinator."""

from unittest.mock import MagicMock

from homeassistant.components.sunweg.const import DeviceType
from homeassistant.components.sunweg.coordinator import SunWEGDataUpdateCoordinator
from homeassistant.core import HomeAssistant


async def test_get_api_value_wrong_inverter(hass: HomeAssistant, plant_fixture) -> None:
    """Test get_api_value with wrong inverter attribute."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    await coordinator.async_refresh()
    assert coordinator.get_api_value("today_energy", DeviceType.INVERTER, 0) is None


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
