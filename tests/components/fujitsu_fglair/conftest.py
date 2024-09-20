"""Common fixtures for the Fujitsu HVAC (based on Ayla IOT) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, create_autospec, patch

from ayla_iot_unofficial import AylaApi
from ayla_iot_unofficial.fujitsu_hvac import FanSpeed, FujitsuHVAC, OpMode, SwingMode
import pytest

from homeassistant.components.fujitsu_fglair.const import (
    CONF_REGION,
    DOMAIN,
    REGION_DEFAULT,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_DEVICE_NAME = "Test device"
TEST_DEVICE_SERIAL = "testserial"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"

TEST_USERNAME2 = "test-username2"
TEST_PASSWORD2 = "test-password2"

TEST_SERIAL_NUMBER = "testserial123"
TEST_SERIAL_NUMBER2 = "testserial345"

TEST_PROPERTY_VALUES = {
    "model_name": "mock_fujitsu_device",
    "mcu_firmware_version": "1",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fujitsu_fglair.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ayla_api(mock_devices: list[AsyncMock]) -> Generator[AsyncMock]:
    """Override AylaApi creation."""
    my_mock = create_autospec(AylaApi)

    with (
        patch(
            "homeassistant.components.fujitsu_fglair.new_ayla_api", return_value=my_mock
        ),
        patch(
            "homeassistant.components.fujitsu_fglair.config_flow.new_ayla_api",
            return_value=my_mock,
        ),
    ):
        my_mock.async_get_devices.return_value = mock_devices
        yield my_mock


@pytest.fixture
def mock_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Return a regular config entry."""
    region = REGION_DEFAULT
    if hasattr(request, "param"):
        region = request.param

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_REGION: region,
        },
    )


def _create_device(serial_number: str) -> AsyncMock:
    dev = AsyncMock(spec=FujitsuHVAC)
    dev.device_serial_number = serial_number
    dev.device_name = serial_number
    dev.property_values = TEST_PROPERTY_VALUES
    dev.has_capability.return_value = True
    dev.fan_speed = FanSpeed.AUTO
    dev.supported_fan_speeds = [
        FanSpeed.LOW,
        FanSpeed.MEDIUM,
        FanSpeed.HIGH,
        FanSpeed.AUTO,
    ]
    dev.op_mode = OpMode.COOL
    dev.supported_op_modes = [
        OpMode.OFF,
        OpMode.ON,
        OpMode.AUTO,
        OpMode.COOL,
        OpMode.DRY,
    ]
    dev.swing_mode = SwingMode.SWING_BOTH
    dev.supported_swing_modes = [
        SwingMode.OFF,
        SwingMode.SWING_HORIZONTAL,
        SwingMode.SWING_VERTICAL,
        SwingMode.SWING_BOTH,
    ]
    dev.temperature_range = [18.0, 26.0]
    dev.sensed_temp = 22.0
    dev.set_temp = 21.0

    return dev


@pytest.fixture
def mock_devices() -> list[AsyncMock]:
    """Generate a list of mock devices that the API can return."""
    return [
        _create_device(serial) for serial in (TEST_SERIAL_NUMBER, TEST_SERIAL_NUMBER2)
    ]
