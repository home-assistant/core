"""Test module for IoTMeter sensor entities in Home Assistant."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.iotmeter.const import DOMAIN
from homeassistant.components.iotmeter.sensor import (
    ConsumptionEnergySensor,
    EvseSensor,
    GenerationEnergySensor,
    TotalPowerSensor,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_total_power_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test total power sensor."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = {
        "P1": 1000,
        "P2": 2000,
        "P3": 3000,
    }
    mock_coordinator.async_request_refresh = AsyncMock(return_value=None)
    hass.data[DOMAIN] = {"coordinator": mock_coordinator}
    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="iotmeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    await async_setup_entry(hass, config_entry, lambda entities: None)
    await hass.async_block_till_done()

    sensor = TotalPowerSensor(mock_coordinator, "Total Power", {}, "kW")
    assert sensor.state == 6.0
    assert sensor.extra_state_attributes == {"P1": 1.0, "P2": 2.0, "P3": 3.0}
    assert sensor.icon == "mdi:home-lightning-bolt"


async def test_consumption_energy_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test consumption energy sensor."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = {
        "E1tP": 1000,
        "E2tP": 2000,
        "E3tP": 3000,
    }
    mock_coordinator.async_request_refresh = AsyncMock(return_value=None)
    hass.data[DOMAIN] = {"coordinator": mock_coordinator}

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    await async_setup_entry(hass, config_entry, lambda entities: None)
    await hass.async_block_till_done()

    sensor = ConsumptionEnergySensor(mock_coordinator, "Consumption Energy", {}, "kWh")
    assert sensor.state == 6
    assert sensor.icon == "mdi:transmission-tower"


async def test_generation_energy_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test generation energy sensor."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = {
        "E1tN": 4000,
        "E2tN": 5000,
        "E3tN": 6000,
    }
    mock_coordinator.async_request_refresh = AsyncMock(return_value=None)
    hass.data[DOMAIN] = {"coordinator": mock_coordinator}

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    await async_setup_entry(hass, config_entry, lambda entities: None)
    await hass.async_block_till_done()

    sensor = GenerationEnergySensor(mock_coordinator, "Generation Energy", {}, "kWh")
    assert sensor.state == 15
    assert sensor.icon == "mdi:solar-power-variant"


async def test_evse_sensor(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test EVSE sensor."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = {"EV_STATE": [2]}
    mock_coordinator.async_request_refresh = AsyncMock(return_value=None)
    hass.data[DOMAIN] = {"coordinator": mock_coordinator}

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    await async_setup_entry(hass, config_entry, lambda entities: None)
    await hass.async_block_till_done()

    translations = {"component.iotmeter.entity.sensor.evse_status.2": "Charging"}
    sensor = EvseSensor(mock_coordinator, "EVSE", translations, None)
    assert sensor.state == "Charging"
    assert sensor.icon == "mdi:ev-station"
