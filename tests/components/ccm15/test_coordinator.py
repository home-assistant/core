"""Unit test for CCM15 coordinator component."""
import unittest
from unittest.mock import AsyncMock, patch

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
from homeassistant.const import (
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_coordinator(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the coordinator."""
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator._fetch_xml_data",
        return_value="<response><a0>000000b0b8001b,</a0><a1>00000041c0001a,</a1><a2>-</a2></response>",
    ):
        coordinator = CCM15Coordinator("1.1.1.1", "80", 30, hass)
        await coordinator.async_refresh()
        data = coordinator.data
        devices = coordinator.get_devices()

    assert len(data.devices) == 2
    first_climate = data.devices[0]
    assert first_climate is not None
    assert first_climate.temperature == 27
    assert first_climate.temperature_setpoint == 23
    assert first_climate.unit == UnitOfTemperature.CELSIUS

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
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator.async_send_state",
        return_value=200,
    ):
        await climate.async_set_fan_mode(FAN_HIGH)

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator.async_send_state",
        return_value=200,
    ):
        await climate.async_set_hvac_mode(HVACMode.COOL)

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator.async_send_state",
        return_value=200,
    ):
        await climate.async_set_temperature(ATTR_TEMPERATURE=25)
        await climate.async_set_temperature(**{ATTR_TEMPERATURE: 25})

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator.async_send_state",
        return_value=200,
    ):
        await climate.async_turn_off()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator.async_send_state",
        return_value=200,
    ):
        await climate.async_turn_on()


if __name__ == "__main__":
    unittest.main()
