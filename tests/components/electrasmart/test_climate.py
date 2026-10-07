"""Tests for the Electra Smart climate entity."""

from unittest.mock import AsyncMock, Mock, patch

from electrasmart.device import OperationMode
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.components.electrasmart.const import (
    CONF_IMEI,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "climate.living_room"


@pytest.fixture(name="mock_device")
def mock_device_fixture() -> Mock:
    """Return a mocked Electra AC device that has a mode to restore."""
    device = Mock(
        mac="a8032ab12345",
        model="Electra A/C",
        manufactor="Electra",
        features=[],
        is_disconnected=Mock(return_value=False),
        is_on=Mock(return_value=False),
        is_horizontal_swing=Mock(return_value=False),
        is_vertical_swing=Mock(return_value=False),
        get_fan_speed=Mock(return_value=OperationMode.FAN_SPEED_AUTO),
        get_mode=Mock(return_value=OperationMode.MODE_COOL),
        get_sensor_temperature=Mock(return_value=24),
        get_temperature=Mock(return_value=22),
        get_shabat_mode=Mock(return_value=False),
        turn_on=Mock(return_value=True),
        turn_off=Mock(return_value=None),
        set_mode=Mock(return_value=None),
    )
    # `name` is a reserved Mock kwarg, so it must be set after construction.
    device.name = "Living Room"
    return device


@pytest.fixture(name="mock_api")
def mock_api_fixture(mock_device: Mock) -> Mock:
    """Return a mocked Electra API that accepts state changes."""
    return Mock(
        devices=[mock_device],
        fetch_devices=AsyncMock(),
        set_state=AsyncMock(return_value={"status": 0, "data": {"res": 0}}),
    )


async def _async_setup_entry(hass: HomeAssistant, mock_api: Mock) -> None:
    """Set up the integration with a single mocked AC."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0521234567",
        data={
            CONF_TOKEN: "token",
            CONF_IMEI: "2b950000024051000000000000000000",
            CONF_PHONE_NUMBER: "0521234567",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_turn_on_keeps_the_mode_the_ac_was_last_running_in(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Turning on must not force a mode on the device."""
    await _async_setup_entry(hass, mock_api)

    await hass.services.async_call(
        CLIMATE_DOMAIN, "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_not_called()
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_turn_on_falls_back_to_cool_when_no_mode_can_be_restored(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """A unit that reports no previous mode must still turn on."""
    mock_device.turn_on = Mock(return_value=False)
    await _async_setup_entry(hass, mock_api)

    await hass.services.async_call(
        CLIMATE_DOMAIN, "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_turn_off_turns_the_device_off(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Turning off goes through set_hvac_mode, which calls turn_off()."""
    await _async_setup_entry(hass, mock_api)

    await hass.services.async_call(
        CLIMATE_DOMAIN, "turn_off", {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_device.turn_off.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_set_hvac_mode_still_selects_the_requested_mode(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Explicitly picking a mode must keep working."""
    await _async_setup_entry(hass, mock_api)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )

    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_device.turn_on.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)
