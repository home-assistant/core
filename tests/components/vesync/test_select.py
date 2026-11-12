"""Tests for the select platform."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
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
    _set_purifier_auto_preference,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT, mock_devices_response


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


@pytest.mark.parametrize(
    ("room_size", "expected_args"),
    [
        pytest.param(400, ("quiet", 400), id="room_size"),
        pytest.param(0, ("quiet",), id="no_room_size"),
    ],
)
async def test_purifier_auto_preference(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    room_size: int,
    expected_args: tuple[str | int, ...],
) -> None:
    """Test the purifier auto mode preference select."""
    mock_devices_response(aioclient_mock, "Air Purifier Vital 200S")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "select.air_purifier_vital_200s_auto_mode_preference"
    assert hass.states.get(entity_id).state == "default"

    device = config_entry.runtime_data.manager.devices.air_purifiers[0]
    device.state.auto_room_size = room_size

    with patch(
        "pyvesync.devices.vesyncpurifier.VeSyncAirBaseV2.set_auto_preference",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: "quiet",
            },
            blocking=True,
        )

    method_mock.assert_awaited_once_with(*expected_args)


async def test_no_auto_preference_without_support(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a purifier that reports no auto preference gets no select."""
    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("fan.air_purifier_200s") is not None
    assert hass.states.get("select.air_purifier_200s_auto_mode_preference") is None


def test_auto_preference_unsupported_device() -> None:
    """Test setting an auto preference on a device without one raises."""
    with pytest.raises(HomeAssistantError):
        _set_purifier_auto_preference(Mock(spec=[]), "quiet")
