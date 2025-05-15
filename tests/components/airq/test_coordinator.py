"""Test the air-Q coordinator."""

import logging
from unittest.mock import patch

from aioairq import DeviceInfo as AirQDeviceInfo
import pytest

from homeassistant.components.airq import AirQCoordinator
from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")
MOCKED_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_IP_ADDRESS: "192.168.0.0",
        CONF_PASSWORD: "password",
    },
    unique_id="123-456",
)

TEST_DEVICE_INFO = AirQDeviceInfo(
    id="id",
    name="name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)
TEST_DEVICE_DATA = {"co2": 500.0, "Status": "OK"}
STATUS_WARMUP = {
    "co": "co sensor still in warm up phase; waiting time = 18 s",
    "tvoc": "tvoc sensor still in warm up phase; waiting time = 18 s",
    "so2": "so2 sensor still in warm up phase; waiting time = 17 s",
}


async def test_logging_in_coordinator_first_update_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the first AirQCoordinator._async_update_data call logs necessary setup.

    The fields of AirQCoordinator.device_info that are specific to the device are only
    populated upon the first call to AirQCoordinator._async_update_data. The one field
    which is actually necessary is 'name', and its absence is checked and logged,
    as well as its being set.
    """
    caplog.set_level(logging.DEBUG)
    coordinator = AirQCoordinator(hass, MOCKED_ENTRY)

    # check that the name _is_ missing
    assert "name" not in coordinator.device_info

    # First call: fetch missing device info
    with (
        patch("aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO),
        patch("aioairq.AirQ.get_latest_data", return_value=TEST_DEVICE_DATA),
        patch("aioairq.AirQ.get_current_brightness", return_value=6.0),
    ):
        await coordinator._async_update_data()

    # check that the missing name is logged...
    assert (
        "'name' not found in AirQCoordinator.device_info, fetching from the device"
        in caplog.text
    )
    # ...and fixed
    assert coordinator.device_info.get("name") == TEST_DEVICE_INFO["name"]
    assert (
        f"Updated AirQCoordinator.device_info for 'name' {TEST_DEVICE_INFO['name']}"
        in caplog.text
    )

    # Also that no warming up sensors is found as none are mocked
    assert "Following sensors are still warming up" not in caplog.text


async def test_logging_in_coordinator_subsequent_update_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the second AirQCoordinator._async_update_data call has nothing to log.

    The second call is emulated by setting up AirQCoordinator.device_info correctly,
    instead of actually calling the _async_update_data, which would populate the log
    with the messages we want to see not being repeated.
    """
    caplog.set_level(logging.DEBUG)
    coordinator = AirQCoordinator(hass, MOCKED_ENTRY)
    coordinator.device_info.update(DeviceInfo(**TEST_DEVICE_INFO))

    with (
        patch("aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO),
        patch("aioairq.AirQ.get_latest_data", return_value=TEST_DEVICE_DATA),
        patch("aioairq.AirQ.get_current_brightness", return_value=6.0),
    ):
        await coordinator._async_update_data()
    # check that the name _is not_ missing
    assert "name" in coordinator.device_info
    # and that nothing of the kind is logged
    assert (
        "'name' not found in AirQCoordinator.device_info, fetching from the device"
        not in caplog.text
    )
    assert (
        f"Updated AirQCoordinator.device_info for 'name' {TEST_DEVICE_INFO['name']}"
        not in caplog.text
    )


async def test_logging_when_warming_up_sensor_present(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that warming up sensors are logged."""
    caplog.set_level(logging.DEBUG)
    coordinator = AirQCoordinator(hass, MOCKED_ENTRY)
    with (
        patch("aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO),
        patch(
            "aioairq.AirQ.get_latest_data",
            return_value=TEST_DEVICE_DATA | {"Status": STATUS_WARMUP},
        ),
        patch("aioairq.AirQ.get_current_brightness", return_value=6.0),
    ):
        await coordinator._async_update_data()
    assert (
        f"Following sensors are still warming up: {set(STATUS_WARMUP.keys())}"
        in caplog.text
    )
