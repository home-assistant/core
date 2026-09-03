"""Common fixtures for the WATERCryst BIOCAT tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import HTTPStatusError, Request, RequestError, Response
from pyocat.models import (
    DeviceResponse,
    EventResponse,
    MeasurementResponse,
    ModeResponse,
    StateResponse,
    WaterProtectionResponse,
)
import pytest

from homeassistant.components.watercryst import RuntimeData
from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from tests.common import MockConfigEntry

DEVICE_NAME = "HA Device"
BIOCAT_SERIAL = "2026123456789123"
DEVICE_TYPE_NUMBER = "12000273"
DEVICE_TYPE_LINE = "BIOCAT"
DEVICE_TYPE_SERIES = "KLS 3000-C"
FW_VERSION = "V01.05.07"
HW_VERSION = "2"
SYSTEM_MAC = "00:A2:AA:BB:CC:DD"


DEFAULT_INFO_RESPONSE = DeviceResponse(
    biocat_serial=BIOCAT_SERIAL,
    electronics_serial="0123456789",
    device_type_number=DEVICE_TYPE_NUMBER,
    line=DEVICE_TYPE_LINE,
    series=DEVICE_TYPE_SERIES,
    has_flow_rate_sensor=True,
    has_leakage_protection_system=True,
    has_lime_scale_protection=True,
    has_pressure_sensor=True,
    has_temperature_sensor=True,
    has_wireless_sensor_option=True,
    name=DEVICE_NAME,
    current_firmware_version=FW_VERSION,
    current_hardware_version=HW_VERSION,
    latest_firmware_version="V01.08.05",
    system_mac_address=SYSTEM_MAC,
)

DEFAULT_MEASUREMENT_RESPONSE = MeasurementResponse(
    water_temp=24,
    pressure=3.68,
    flow_rate=5.41,
    todays_consumption=31.11,
    total_consumption=532.34,
    last_water_tap_volume=4.23,
    last_water_tap_duration=15,
)

DEFAULT_STATE_RESPONSE = StateResponse(
    online=True,
    mode=ModeResponse(id="WT", name="Water Treatment"),
    event=EventResponse(
        type="event",
        event_id=0,
        category="info",
        title="Unknown Event",
        description="Unknown Event",
        timestamp=datetime(2026, 6, 8, 13, 13, tzinfo=UTC),
    ),
    water_protection=WaterProtectionResponse(
        absence_mode_enabled=False,
        pause_leakage_protection_until_utc=datetime(2026, 6, 8, 13, 13, tzinfo=UTC),
    ),
    ml_state="success",
)

OFFLINE_STATE_RESPONSE = StateResponse(online=False)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watercryst.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Default config entry mock."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WATERCryst",
        unique_id=BIOCAT_SERIAL,
        entry_id="6D9GB5RKL9691HH3RT895JNH56",
        data={CONF_API_KEY: "<api-key>"},
    )
    entry.runtime_data = RuntimeData(
        biocat_serial_number=BIOCAT_SERIAL,
        has_flow_rate_sensor=True,
        has_leakage_protection_system=True,
        has_pressure_sensor=True,
        has_temperature_sensor=True,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, BIOCAT_SERIAL)},
            connections={
                (CONNECTION_NETWORK_MAC, SYSTEM_MAC),
            },
            manufacturer="WATERCryst",
            model=f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}",
            model_id=DEVICE_TYPE_NUMBER,
            name=DEVICE_NAME,
            serial_number=BIOCAT_SERIAL,
            sw_version=FW_VERSION,
            hw_version=HW_VERSION,
            configuration_url=f"https://app.watercryst.com/devices/{BIOCAT_SERIAL}",
        ),
        client=MagicMock(),
        measurements=MagicMock(),
        state=MagicMock(),
    )
    return entry


@pytest.fixture
async def mock_api_client() -> AsyncGenerator[AsyncMock]:
    """Mock WATERCryst Smart Home client."""
    with (
        patch("homeassistant.components.watercryst.AsyncApiClient") as mock,
        patch(
            "homeassistant.components.watercryst.config_flow.AsyncApiClient", new=mock
        ),
    ):
        client = mock.return_value

        client.get_device_info = AsyncMock(return_value=DEFAULT_INFO_RESPONSE)
        client.get_measurements = AsyncMock(return_value=DEFAULT_MEASUREMENT_RESPONSE)
        client.get_state = AsyncMock(return_value=DEFAULT_STATE_RESPONSE)

        yield client


def http_status_error(status_code: int) -> HTTPStatusError:
    """Create an HTTP status error."""
    request = Request("GET", "https://example.com/v1/state")
    response = Response(status_code, request=request)
    return HTTPStatusError(
        "Unexpected HTTP status",
        request=request,
        response=response,
    )


def request_error() -> RequestError:
    """Create a request error."""
    return RequestError(
        message="",
        request=Request("GET", "https://example.com/v1/state"),
    )
