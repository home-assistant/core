"""Tests for ActronAir Climate Entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.actronair.climate import (
    ActronAirClimate,
    ActronAirZoneClimate,
)
from homeassistant.components.actronair.const import DOMAIN
from homeassistant.components.actronair.coordinator import (
    ActronAirSystemStatusDataCoordinator,
)
from homeassistant.components.climate import FAN_AUTO, FAN_HIGH, HVACMode


### ✅ **1. Test ActronAirClimate (Wall Controller) Initialization**
@pytest.mark.asyncio
async def test_actronair_climate_entity() -> None:
    """Test initialization of ActronAir Wall Controller climate entity."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = AsyncMock()
    mock_coordinator.acSystemStatus.SystemName = "Main AC"
    mock_coordinator.acSystemStatus.MasterSerial = "12345"
    mock_coordinator.acSystemStatus.IsOn = True
    mock_coordinator.acSystemStatus.Mode = "COOL"
    mock_coordinator.acSystemStatus.TemprSetPoint_Cool = 24
    mock_coordinator.acSystemStatus.LiveTemp_oC = 22
    mock_coordinator.acSystemStatus.LiveHumidity_pc = 60

    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    assert entity.name == "AC Main AC (12345)"
    assert entity.unique_id == f"{DOMAIN}_12345_climate"
    assert entity.hvac_mode == HVACMode.COOL
    assert entity.target_temperature == 24
    assert entity.current_temperature == 22
    assert entity.current_humidity == 60


### ✅ **2. Test ActronAirClimate HVAC Mode Handling**
@pytest.mark.asyncio
async def test_actronair_climate_set_hvac_mode() -> None:
    """Test setting HVAC mode in ActronAir Wall Controller."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    with pytest.raises(ValueError):
        await entity.async_set_hvac_mode("INVALID_MODE")

    await entity.async_set_hvac_mode(HVACMode.COOL)
    assert entity.hvac_mode == HVACMode.COOL

    await entity.async_set_hvac_mode(HVACMode.OFF)
    assert entity.hvac_mode == HVACMode.OFF


### ✅ **3. Test ActronAirClimate Fan Mode Handling**
@pytest.mark.asyncio
async def test_actronair_climate_set_fan_mode() -> None:
    """Test setting fan mode in ActronAir Wall Controller."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    with pytest.raises(ValueError):
        await entity.async_set_fan_mode("INVALID_FAN")

    await entity.async_set_fan_mode(FAN_HIGH)
    assert entity.fan_mode == FAN_HIGH

    await entity.async_set_fan_mode(FAN_AUTO)
    assert entity.fan_mode == FAN_AUTO


### ✅ **4. Test ActronAirClimate Temperature Adjustment**
@pytest.mark.asyncio
async def test_actronair_climate_set_temperature() -> None:
    """Test setting target temperature in ActronAir Wall Controller."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    await entity.async_set_temperature(temperature=26)
    assert entity.target_temperature == 26


### ✅ **5. Test ActronAirZoneClimate (Zone Entity) Initialization**
@pytest.mark.asyncio
async def test_actronair_zone_climate_entity() -> None:
    """Test initialization of ActronAir Zone climate entity."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = AsyncMock()
    mock_coordinator.acSystemStatus.RemoteZoneInfo = [{"NV_Title": "Living Room"}]
    mock_coordinator.acSystemStatus.EnabledZones = [True]

    entity = ActronAirZoneClimate(mock_coordinator, "12345", 1)

    assert entity.name == "Living Room"
    assert entity.unique_id == f"{DOMAIN}_zone_1_climate"
    assert entity.hvac_mode == HVACMode.HEAT_COOL


### ✅ **6. Test ActronAirZoneClimate Zone Toggle (On/Off)**
@pytest.mark.asyncio
async def test_actronair_zone_climate_toggle() -> None:
    """Test turning zone on and off."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = AsyncMock()
    mock_coordinator.acSystemStatus.EnabledZones = [True]

    entity = ActronAirZoneClimate(mock_coordinator, "12345", 1)

    await entity.async_set_hvac_mode(HVACMode.OFF)
    assert entity.hvac_mode == HVACMode.OFF

    await entity.async_set_hvac_mode(HVACMode.HEAT_COOL)
    assert entity.hvac_mode == HVACMode.HEAT_COOL
