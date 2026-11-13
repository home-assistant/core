"""Tests for the select platform."""

from unittest.mock import MagicMock, Mock

import pytest
from pyvesync.const import DeviceStatus
from pyvesync.utils.errors import ResponseInfo

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.vesync.const import (
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF,
)
from homeassistant.components.vesync.select import (
    HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_set_nightlight_level(
    hass: HomeAssistant, humidifier_300s, install_humidifier_device
) -> None:
    """Test set of humidifier night light level."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
            SelectServiceArgument.OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
        },
        blocking=True,
    )

    # Assert that setter API was invoked with the expected translated value
    humidifier_300s.set_nightlight_brightness.assert_called_once_with(
        HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP[HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM]
    )


@pytest.mark.parametrize(
    ("brightness", "nightlight_status", "expected_state"),
    [
        pytest.param(0, DeviceStatus.OFF, HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF, id="off"),
        pytest.param(50, DeviceStatus.ON, HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM, id="dim"),
        pytest.param(
            100, DeviceStatus.ON, HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT, id="bright"
        ),
        pytest.param(12, DeviceStatus.ON, STATE_UNKNOWN, id="sprout-brightness"),
        pytest.param(75, DeviceStatus.ON, STATE_UNKNOWN, id="intermediate-brightness"),
        pytest.param(None, DeviceStatus.ON, STATE_UNKNOWN, id="missing-brightness"),
    ],
)
async def test_humidifier_nightlight_level(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: MagicMock,
    humidifier_300s: Mock,
    brightness: int | None,
    nightlight_status: DeviceStatus,
    expected_state: str,
) -> None:
    """Test the state of humidifier night light level select entity."""
    humidifier_300s.state.nightlight_brightness = brightness
    humidifier_300s.state.nightlight_status = nightlight_status
    manager.devices.humidifiers.append(humidifier_300s)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
        == expected_state
    )


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
@pytest.mark.parametrize(
    ("last_response", "message"),
    [
        pytest.param(
            ResponseInfo(name="error", error_type="error", message="Device error"),
            "Device error",
            id="last_response",
        ),
        pytest.param(
            None,
            "Unknown error selecting option, no response.",
            id="no_last_response",
        ),
    ],
)
@pytest.mark.usefixtures("install_humidifier_device")
async def test_select_option_device_failure(
    hass: HomeAssistant,
    humidifier_300s: Mock,
    last_response: ResponseInfo | None,
    message: str,
) -> None:
    """Test an error is raised when the device rejects the option."""
    humidifier_300s.set_nightlight_brightness.return_value = False
    humidifier_300s.last_response = last_response

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
                SelectServiceArgument.OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
            },
            blocking=True,
        )
