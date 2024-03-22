"""Test for the FujitsuHVACCoordinator."""
from unittest.mock import AsyncMock, Mock

from ayla_iot_unofficial import AylaAuthError
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC
import pytest

from homeassistant.components.fujitsu_hvac.coordinator import FujitsuHVACCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

TEST_SERIAL_NUMBER = "testserial123"
TEST_SERIAL_NUMBER2 = "testserial345"


async def test_coordinator_initial_data(hass: HomeAssistant) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    devicemock = AsyncMock(spec=FujitsuHVAC)
    devicemock.device_serial_number = TEST_SERIAL_NUMBER

    apimock = AsyncMock()
    apimock.async_get_devices.return_value = [devicemock]

    coordinator = FujitsuHVACCoordinator(hass, apimock)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {TEST_SERIAL_NUMBER: devicemock}


async def test_coordinator_filtered_data(hass: HomeAssistant) -> None:
    """Test that coordinator returns the data we expect when it has listeners."""
    devicemock = AsyncMock(spec=FujitsuHVAC)
    devicemock.device_serial_number = TEST_SERIAL_NUMBER

    devicemock2 = AsyncMock(spec=FujitsuHVAC)
    devicemock2.device_serial_number = TEST_SERIAL_NUMBER2

    apimock = AsyncMock()
    apimock.async_get_devices.return_value = [devicemock, devicemock2]

    coordinator = FujitsuHVACCoordinator(hass, apimock)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {
        TEST_SERIAL_NUMBER: devicemock,
        TEST_SERIAL_NUMBER2: devicemock2,
    }

    coordinator.async_add_listener(Mock(), TEST_SERIAL_NUMBER)

    await coordinator.async_refresh()

    assert coordinator.data == {TEST_SERIAL_NUMBER: devicemock}


async def test_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test that coordinator raises ConfigEntryAuthFailed when API raises an auth error."""
    apimock = AsyncMock()
    apimock.async_get_devices.side_effect = AylaAuthError

    coordinator = FujitsuHVACCoordinator(hass, apimock)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_device_auth_error(hass: HomeAssistant) -> None:
    """Test that coordinator raises ConfigEntryAuthFailed when device update raises an auth error."""
    devicemock = AsyncMock(spec=FujitsuHVAC)
    devicemock.async_update.side_effect = AylaAuthError
    apimock = AsyncMock()
    apimock.async_get_devices.return_value = [devicemock]

    coordinator = FujitsuHVACCoordinator(hass, apimock)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()
