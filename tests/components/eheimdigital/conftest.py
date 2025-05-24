"""Configurations for the EHEIM Digital tests."""

from collections.abc import Generator
from datetime import time, timedelta, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.heater import EheimDigitalHeater
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import (
    CCVPacket,
    ClockPacket,
    EheimDeviceType,
    FilterErrorCode,
    FilterMode,
    HeaterMode,
    HeaterUnit,
    MsgTitle,
    UsrDtaPacket,
)
import pytest

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "eheimdigital"}, unique_id="00:00:00:00:00:01"
    )


@pytest.fixture
def classic_led_ctrl_mock():
    """Mock a classicLEDcontrol device."""
    classic_led_ctrl_mock = MagicMock(spec=EheimDigitalClassicLEDControl)
    classic_led_ctrl_mock.usrdta = UsrDtaPacket(
        {
            "aqName": "Mock Aquarium",
            "demoUse": 0,
            "dst": 0,
            "emailAddr": "",
            "firmwareAvailable": 0,
            "firstStart": 0,
            "from": "00:00:00:00:00:01",
            "groupID": 0,
            "host": "",
            "language": "DE",
            "latestAvailableRevision": [-1, -1],
            "liveTime": 10,
            "meshing": 1,
            "name": "Mock classicLEDcontrol+e",
            "netmode": "ST",
            "power": "",
            "remote": 0,
            "revision": [1000, 1000],
            "sysLED": 20,
            "tankconfig": '[["CLASSIC_DAYLIGHT"], []]',
            "tID": 0,
            "timezone": 60,
            "title": MsgTitle.USRDTA,
            "to": "USER",
            "unit": 0,
            "usrName": "",
            "version": EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E,
        }
    )
    classic_led_ctrl_mock.ccv = CCVPacket(
        {
            "title": MsgTitle.CCV,
            "from": "00:00:00:00:00:01",
            "to": "USER",
            "currentValues": [10, 39],
        }
    )
    classic_led_ctrl_mock.clock = ClockPacket(
        {
            "title": MsgTitle.CLOCK,
            "from": "00:00:00:00:00:01",
            "year": 2025,
            "month": 3,
            "day": 10,
            "hour": 11,
            "min": 0,
            "sec": 45,
            "mode": "DAYCL_MODE",
            "valid": 1,
        }
    )
    classic_led_ctrl_mock.tankconfig = json.loads(
        classic_led_ctrl_mock.usrdta["tankconfig"]
    )
    return classic_led_ctrl_mock


@pytest.fixture
def heater_mock():
    """Mock a Heater device."""
    heater_mock = MagicMock(spec=EheimDigitalHeater)
    heater_mock.mac_address = "00:00:00:00:00:02"
    heater_mock.device_type = EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    heater_mock.name = "Mock Heater"
    heater_mock.aquarium_name = "Mock Aquarium"
    heater_mock.sw_version = "1.0.0_1.0.0"
    heater_mock.temperature_unit = HeaterUnit.CELSIUS
    heater_mock.current_temperature = 24.2
    heater_mock.target_temperature = 25.5
    heater_mock.temperature_offset = 0.1
    heater_mock.night_temperature_offset = -0.2
    heater_mock.is_heating = True
    heater_mock.is_active = True
    heater_mock.operation_mode = HeaterMode.MANUAL
    heater_mock.day_start_time = time(8, 0, tzinfo=timezone(timedelta(hours=1)))
    heater_mock.night_start_time = time(20, 0, tzinfo=timezone(timedelta(hours=1)))
    heater_mock.sys_led = 20
    return heater_mock


@pytest.fixture
def classic_vario_mock():
    """Mock a classicVARIO device."""
    classic_vario_mock = MagicMock(spec=EheimDigitalClassicVario)
    classic_vario_mock.mac_address = "00:00:00:00:00:03"
    classic_vario_mock.device_type = EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    classic_vario_mock.name = "Mock classicVARIO"
    classic_vario_mock.aquarium_name = "Mock Aquarium"
    classic_vario_mock.sw_version = "1.0.0_1.0.0"
    classic_vario_mock.current_speed = 75
    classic_vario_mock.manual_speed = 75
    classic_vario_mock.day_speed = 80
    classic_vario_mock.day_start_time = time(8, 0, tzinfo=timezone(timedelta(hours=1)))
    classic_vario_mock.night_start_time = time(
        20, 0, tzinfo=timezone(timedelta(hours=1))
    )
    classic_vario_mock.night_speed = 20
    classic_vario_mock.is_active = True
    classic_vario_mock.filter_mode = FilterMode.MANUAL
    classic_vario_mock.error_code = FilterErrorCode.NO_ERROR
    classic_vario_mock.service_hours = 360
    return classic_vario_mock


@pytest.fixture
def eheimdigital_hub_mock(
    classic_led_ctrl_mock: MagicMock,
    heater_mock: MagicMock,
    classic_vario_mock: MagicMock,
) -> Generator[AsyncMock]:
    """Mock eheimdigital hub."""
    with (
        patch(
            "homeassistant.components.eheimdigital.coordinator.EheimDigitalHub",
            spec=EheimDigitalHub,
        ) as eheimdigital_hub_mock,
        patch(
            "homeassistant.components.eheimdigital.config_flow.EheimDigitalHub",
            new=eheimdigital_hub_mock,
        ),
    ):
        eheimdigital_hub_mock.return_value.devices = {
            "00:00:00:00:00:01": classic_led_ctrl_mock,
            "00:00:00:00:00:02": heater_mock,
            "00:00:00:00:00:03": classic_vario_mock,
        }
        eheimdigital_hub_mock.return_value.main = classic_led_ctrl_mock
        yield eheimdigital_hub_mock


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Initialize the integration."""

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.eheimdigital.coordinator.asyncio.Event", new=AsyncMock
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
