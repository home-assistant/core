"""Common fixtures for the Fujitsu HVAC (based on Ayla IOT) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, create_autospec, patch

from ayla_iot_unofficial import AylaApi
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC
import pytest

from homeassistant.components.fujitsu_hvac.const import CONF_EUROPE, DOMAIN
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
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fujitsu_hvac.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ayla_api() -> Generator[AsyncMock]:
    """Override AylaApi creation."""
    mymock = create_autospec(AylaApi)

    with (
        patch(
            "homeassistant.components.fujitsu_hvac.new_ayla_api", return_value=mymock
        ),
        patch(
            "homeassistant.components.fujitsu_hvac.config_flow.new_ayla_api",
            return_value=mymock,
        ),
    ):
        yield mymock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a regular config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: False,
        },
    )


@pytest.fixture
def mock_devices() -> list[AsyncMock]:
    """Generate a list of mock devices that the API can return."""
    devices = [AsyncMock(spec=FujitsuHVAC) for i in range(2)]

    devices[0].device_serial_number = TEST_SERIAL_NUMBER
    devices[0].device_name = TEST_SERIAL_NUMBER
    devices[0].property_values = TEST_PROPERTY_VALUES

    devices[1].device_serial_number = TEST_SERIAL_NUMBER2
    devices[1].device_name = TEST_SERIAL_NUMBER2
    devices[1].property_values = TEST_PROPERTY_VALUES

    return devices
