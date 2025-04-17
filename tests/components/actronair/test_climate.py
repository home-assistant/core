"""Tests for ActronAir Climate Entities."""

from unittest.mock import AsyncMock

from actronair_api import SystemStatus, ZoneInfo
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

mock_system_status = SystemStatus(
    SystemName="Living Room AC",
    MasterSerial="ABC123456789",
    LiveTemp_oC=22.5,
    LiveHumidity_pc=45.0,
    IsOnline=True,
    IsOn=True,
    Mode="COOL",
    FanMode="HIGH",
    TemprSetPoint_Cool=23.0,
    TemprSetPoint_Heat=21.0,
    SetCool_Min=18.0,
    SetCool_Max=26.0,
    SetHeat_Min=16.0,
    SetHeat_Max=24.0,
    RemoteZoneInfo=[
        ZoneInfo(
            CanOperate=True,
            CommonZone=False,
            LiveHumidity_pc=50.0,
            LiveTemp_oC=23.5,
            NV_Exists=True,
            NV_Title="Zone 1",
            AirflowControlEnabled=True,
            AirflowControlLocked=False,
            LastZoneProtection=False,
            ZonePosition=1,
            NV_ITC=True,
            NV_ITD=False,
            NV_IHD=True,
            TemprSetPoint_Cool=23.0,
        )
    ],
    EnabledZones=[True],
)


### 1. Test ActronAirClimate (Wall Controller) Initialization**
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


### 2. Test ActronAirClimate HVAC Mode Handling**
@pytest.mark.asyncio
async def test_actronair_climate_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting HVAC mode in ActronAir Wall Controller."""
    mock_config_entry = ConfigEntry(
        entry_id="test_entry",
        domain=DOMAIN,
        title="Test AC System",
        data={},  # Mock data
        options={},  # Mock options
        minor_version=1,  # Correct parameter name
        source="user",  # Mock source
        unique_id="unique_test_id",  # Mock unique_id
        discovery_keys=None,  # Mock discovery hash
        subentries_data={},  # Mock subentries data
        version=1,  # Mock version
    )
    hass.config_entries.async_add(mock_config_entry)
    await hass.async_block_till_done()

    mock_api = AsyncMock()
    mock_api.async_sendCommand.return_value = {"status": "ok"}

    mock_coordinator = ActronAirSystemStatusDataCoordinator(hass, mock_api)
    mock_coordinator.ac_system_status = mock_system_status
    mock_coordinator.async_request_refresh = AsyncMock()
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    await entity.async_set_hvac_mode(HVACMode.COOL)
    mock_coordinator.ac_system_status.IsOn = True
    mock_coordinator.ac_system_status.Mode = "COOL"
    assert entity.hvac_mode == HVACMode.COOL

    await entity.async_set_hvac_mode(HVACMode.OFF)
    mock_coordinator.ac_system_status.IsOn = False
    assert entity.hvac_mode == HVACMode.OFF


### 3. Test ActronAirClimate Fan Mode Handling**
@pytest.mark.asyncio
async def test_actronair_climate_set_fan_mode() -> None:
    """Test setting fan mode in ActronAir Wall Controller."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = mock_system_status
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_api = AsyncMock()
    mock_api.async_sendCommand.return_value = {"status": "ok"}
    mock_coordinator.aa_api = mock_api
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    await entity.async_set_fan_mode(FAN_HIGH)
    mock_coordinator.acSystemStatus.FanMode = "HIGH"
    assert entity.fan_mode == FAN_HIGH

    await entity.async_set_fan_mode(FAN_AUTO)
    mock_coordinator.acSystemStatus.FanMode = "AUTO"
    assert entity.fan_mode == FAN_AUTO


### 4. Test ActronAirClimate Temperature Adjustment**
@pytest.mark.asyncio
async def test_actronair_climate_set_temperature() -> None:
    """Test setting target temperature in ActronAir Wall Controller."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = mock_system_status
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_api = AsyncMock()
    mock_api.async_sendCommand.return_value = {"status": "ok"}
    mock_coordinator.aa_api = mock_api
    entity = ActronAirClimate(mock_coordinator, mock_coordinator, "12345")

    await entity.async_set_temperature(temperature=26)
    mock_coordinator.acSystemStatus.TemprSetPoint_Cool = 26
    assert entity.target_temperature == 26


### 5. Test ActronAirZoneClimate (Zone Entity) Initialization**
@pytest.mark.asyncio
async def test_actronair_zone_climate_entity() -> None:
    """Test initialization of ActronAir Zone climate entity."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = mock_system_status
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_api = AsyncMock()
    mock_api.async_sendCommand.return_value = {"status": "ok"}
    mock_coordinator.aa_api = mock_api
    entity = ActronAirZoneClimate(mock_coordinator, "12345", 1)

    assert entity.name == "Zone 1 - (System is OFF)"
    assert entity.unique_id == f"{DOMAIN}_zone_1_climate"
    mock_coordinator.acSystemStatus.EnabledZones = [True]
    assert entity.hvac_mode == HVACMode.HEAT_COOL


### 6. Test ActronAirZoneClimate Zone Toggle (On/Off)**
@pytest.mark.asyncio
async def test_actronair_zone_climate_toggle() -> None:
    """Test turning zone on and off."""
    mock_coordinator = AsyncMock(spec=ActronAirSystemStatusDataCoordinator)
    mock_coordinator.acSystemStatus = mock_system_status
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_api = AsyncMock()
    mock_api.async_sendCommand.return_value = {"status": "ok"}
    mock_coordinator.aa_api = mock_api
    entity = ActronAirZoneClimate(mock_coordinator, "12345", 1)

    await entity.async_set_hvac_mode(HVACMode.OFF)
    mock_coordinator.acSystemStatus.EnabledZones = [False]
    assert entity.hvac_mode == HVACMode.OFF

    await entity.async_set_hvac_mode(HVACMode.HEAT_COOL)
    mock_coordinator.acSystemStatus.EnabledZones = [True]
    assert entity.hvac_mode == HVACMode.HEAT_COOL
