"""Tests for the Lunatone integration."""

from typing import Final

from lunatone_rest_api_client.models import (
    DALIBusData,
    DeviceData,
    DeviceInfoData,
    DevicesData,
    FeaturesStatus,
    InfoData,
    LineStatus,
)
from lunatone_rest_api_client.models.common import ColorRGBData, ColorWAFData, Status
from lunatone_rest_api_client.models.devices import DeviceStatus

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BASE_URL: Final = "http://10.0.0.131"
PRODUCT_NAME: Final = "Test Product"
SERIAL_NUMBER: Final = 12345
VERSION: Final = "v1.14.1/1.4.3"


DEVICE_INFO_DATA: Final[DeviceInfoData] = DeviceInfoData(
    serial=SERIAL_NUMBER,
    gtin=192837465,
    pcb="2a",
    articleNumber=87654321,
    productionYear=20,
    productionWeek=1,
)
INFO_DATA: Final[InfoData] = InfoData(
    name="Test",
    version=VERSION,
    device=DEVICE_INFO_DATA,
    lines={
        "0": DALIBusData(
            sendBlockedInitialize=False,
            sendBlockedQuiescent=False,
            sendBlockedMacroRunning=False,
            sendBufferFull=False,
            lineStatus=LineStatus.OK,
            device=DEVICE_INFO_DATA,
        ),
        "1": DALIBusData(
            sendBlockedInitialize=False,
            sendBlockedQuiescent=False,
            sendBlockedMacroRunning=False,
            sendBufferFull=False,
            lineStatus=LineStatus.OK,
            device=DeviceInfoData(
                serial=54321,
                gtin=101010101,
                pcb="1a",
                articleNumber=12345678,
                productionYear=22,
                productionWeek=10,
            ),
        ),
    },
)


def build_devices_data() -> DevicesData:
    """Build DevicesData."""
    return DevicesData(devices=build_device_data_list())


def build_device_data_list() -> list[DeviceData]:
    """Build a list of DeviceData."""
    return [
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


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Lunatone integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
