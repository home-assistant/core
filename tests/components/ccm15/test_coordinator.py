"""Unit test for CCM15 coordinator component."""
import unittest
from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import pytest

from homeassistant.components.ccm15 import CCM15Coordinator
from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SWING_OFF,
    SWING_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_coordinator(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the coordinator."""

    # Create a dictionary of CCM15SlaveDevice objects
    ccm15_devices = {
        0: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
        1: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
    }
    # Create an instance of the CCM15DeviceState class
    device_state = CCM15DeviceState(devices=ccm15_devices)
    with patch(
        "ccm15.CCM15Device.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        coordinator = CCM15Coordinator("1.1.1.1", "80", 30, hass)
        await coordinator.async_refresh()

    data = coordinator.data
    devices = coordinator.get_devices()

    assert len(data.devices) == 2
    assert len(devices) == 2

    first_climate = list(devices)[0]
    assert first_climate is not None
    assert first_climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert first_climate.current_temperature == 27
    assert first_climate.target_temperature == 23

    assert len(devices) == 2
    climate = next(iter(devices))
    assert climate is not None
    assert climate.coordinator == coordinator
    assert climate._ac_index == 0
    assert coordinator.data == data
    assert climate.unique_id == "1.1.1.1.0"
    assert climate.name == "Climate0"
    assert climate.hvac_mode == HVACMode.OFF
    assert climate.current_temperature == 27
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.target_temperature == 23
    assert climate.fan_mode == FAN_OFF
    assert climate.swing_mode == SWING_OFF
    assert climate.hvac_modes == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.AUTO,
    ]
    assert climate.extra_state_attributes["error_code"] == 0
    assert climate.should_poll
    device_info = climate.device_info
    assert device_info is not None
    assert device_info["manufacturer"] == "Midea"
    assert climate.supported_features == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    assert climate.swing_modes == [SWING_OFF, SWING_ON]
    assert climate.fan_modes == [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    assert climate.target_temperature_step == 1

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_send_state",
        return_value=200,
    ):
        await climate.async_set_fan_mode(FAN_HIGH)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_send_state",
        return_value=200,
    ):
        await climate.async_set_hvac_mode(HVACMode.COOL)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_send_state",
        return_value=200,
    ):
        await climate.async_set_temperature(ATTR_TEMPERATURE=25)
        await climate.async_set_temperature(**{ATTR_TEMPERATURE: 25})

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_send_state",
        return_value=200,
    ):
        await climate.async_turn_off()

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_send_state",
        return_value=200,
    ):
        await climate.async_turn_on()

    coordinator.data.devices[0] = None
    assert climate.hvac_mode is None
    assert climate.current_temperature is None
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.target_temperature is None
    assert climate.fan_mode is None
    assert climate.swing_mode is None


if __name__ == "__main__":
    unittest.main()
