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
    SensorDaliAddress,
    SensorData,
    SensorsData,
    SensorType,
)
from lunatone_rest_api_client.models.common import ColorRGBData, ColorWAFData, Status
from lunatone_rest_api_client.models.devices import DeviceStatus
from yarl import URL

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BASE_IP: Final = "10.0.0.131"
BASE_URL: Final = URL.build(scheme="http", host=BASE_IP).human_repr()[:-1]
MANUFACTURER: Final = "Lunatone Industrielle Elektronik GmbH"
PRODUCT_NAME: Final = "DALI-2 Display 7''"
SERIAL_NUMBER: Final = 12345
UUID: Final = "be37ca9c-47c2-4498-a38b-c62c7c711840"
VERSION: Final = "v1.14.1/1.4.3"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Lunatone integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def build_info_data(*, include_uuid: bool = True) -> InfoData:
    """Build InfoData."""
    main_device_info_data = DeviceInfoData(
        serial=12345,
        gtin=192837465,
        pcb="2a",
        articleNumber=86456840,
        productionYear=20,
        productionWeek=1,
    )
    return InfoData(
        name="Test",
        version=VERSION,
        uid=UUID if include_uuid else None,
        device=main_device_info_data,
        lines={
            "0": DALIBusData(
                sendBlockedInitialize=False,
                sendBlockedQuiescent=False,
                sendBlockedMacroRunning=False,
                sendBufferFull=False,
                lineStatus=LineStatus.OK,
                device=main_device_info_data,
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
    return DevicesData(
        devices=[
            DeviceData(
                id=1,
                name="Device 1",
                available=True,
                status=DeviceStatus(),
                features=FeaturesStatus(switchable=Status[bool](status=False)),
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
                ),
                address=1,
                line=0,
            ),
            DeviceData(
                id=3,
                name="Device 3",
                available=True,
                status=DeviceStatus(),
                features=FeaturesStatus(
                    switchable=Status[bool](status=False),
                    dimmable=Status[float](status=0.0),
                    colorKelvin=Status[int](status=1000),
                ),
                address=2,
                line=0,
            ),
            DeviceData(
                id=4,
                name="Device 4",
                available=True,
                status=DeviceStatus(),
                features=FeaturesStatus(
                    switchable=Status[bool](status=False),
                    dimmable=Status[float](status=0.0),
                    colorRGB=Status[ColorRGBData](status=ColorRGBData(r=0, g=0, b=0)),
                ),
                address=3,
                line=0,
            ),
            DeviceData(
                id=5,
                name="Device 5",
                available=True,
                status=DeviceStatus(),
                features=FeaturesStatus(
                    switchable=Status[bool](status=False),
                    dimmable=Status[float](status=0.0),
                    colorRGB=Status[ColorRGBData](status=ColorRGBData(r=0, g=0, b=0)),
                    colorWAF=Status[ColorWAFData](status=ColorWAFData(w=0, a=0, f=0)),
                ),
                address=4,
                line=0,
            ),
            DeviceData(
                id=6,
                name="Device 6",
                available=True,
                status=DeviceStatus(),
                features=FeaturesStatus(switchable=Status[bool](status=False)),
                address=0,
                line=1,
            ),
        ]
    )


def build_sensors_data() -> SensorsData:
    """Build SensorsData."""
    return SensorsData(
        sensors=[
            SensorData(
                id=1,
                name="Temperature",
                type=SensorType.TEMPERATURE,
                addressType="internal",
            ),
            SensorData(
                id=2,
                name="Air humidity",
                type=SensorType.AIR_HUMIDITY,
                addressType="internal",
            ),
            SensorData(
                id=3,
                name="Temperature",
                type=SensorType.TEMPERATURE,
                addressType="dali",
                daliSensorAddress=SensorDaliAddress(
                    line=0, address=0, instanceNumber=0
                ),
            ),
        ]
    )
