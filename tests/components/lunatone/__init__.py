"""Tests for the Lunatone integration."""

from typing import Final

from lunatone_rest_api_client.models import (
    DeviceData,
    DeviceInfoData,
    DevicesData,
    FeaturesStatus,
    InfoData,
)
from lunatone_rest_api_client.models.common import ColorRGBData, ColorWAFData, Status
from lunatone_rest_api_client.models.devices import DeviceStatus

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BASE_URL: Final = "http://10.0.0.131"
SERIAL_NUMBER: Final = 12345
VERSION: Final = "v1.14.1/1.4.3"

DEVICE_DATA_LIST: Final[list[DeviceData]] = [
    DeviceData(
        id=1,
        name="Device 1",
        available=True,
        status=DeviceStatus(),
        features=FeaturesStatus(
            switchable=Status[bool](status=False),
            dimmable=Status[float](status=0.0),
            colorKelvin=Status[int](status=1000),
            colorRGB=Status[ColorRGBData](status=ColorRGBData(r=0, g=0, b=0)),
            colorWAF=Status[ColorWAFData](status=ColorWAFData(w=0, a=0, f=0)),
        ),
        address=0,
        line=0,
    ),
    DeviceData(
        id=2,
        name="Device 2",
        available=True,
        status=DeviceStatus(),
        features=FeaturesStatus(
            switchable=Status[bool](status=False),
            dimmable=Status[float](status=0.0),
            colorKelvin=Status[int](status=1000),
            colorRGB=Status[ColorRGBData](status=ColorRGBData(r=0, g=0, b=0)),
            colorWAF=Status[ColorWAFData](status=ColorWAFData(w=0, a=0, f=0)),
        ),
        address=1,
        line=0,
    ),
]
DEVICES_DATA: Final[DevicesData] = DevicesData(devices=DEVICE_DATA_LIST)
INFO_DATA: Final[InfoData] = InfoData(
    name="Test",
    version=VERSION,
    device=DeviceInfoData(
        serial=SERIAL_NUMBER,
        gtin=192837465,
        pcb="2a",
        articleNumber=87654321,
        productionYear=20,
        productionWeek=1,
    ),
)


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Lunatone integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
