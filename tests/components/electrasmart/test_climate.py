"""Tests for the Electra Smart climate entity."""

import logging
from unittest.mock import AsyncMock, Mock, patch

from electrasmart.api import ElectraApiError
from electrasmart.device import OperationMode
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    HVACMode,
)
from homeassistant.components.electrasmart.const import (
    PRESET_NONE,
    PRESET_SHABAT,
    SCAN_INTERVAL_SEC,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_advance_to_next_poll

ENTITY_ID = "climate.living_room"


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_keeps_the_mode_the_ac_was_last_running_in(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Turning on must not force a mode on the device."""
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_not_called()
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_falls_back_to_cool_when_no_mode_can_be_restored(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """A unit that reports no previous mode must still turn on."""
    mock_device.turn_on = Mock(return_value=False)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_turn_off_turns_the_device_off(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Turning off goes through set_hvac_mode, which calls turn_off()."""
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_off.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode_still_selects_the_requested_mode(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Explicitly picking a mode must keep working."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_device.turn_on.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_set_fan_mode(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Setting a fan mode sends the new speed to the API."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: FAN_HIGH},
        blocking=True,
    )

    mock_device.set_fan_speed.assert_called_once_with(OperationMode.FAN_SPEED_HIGH)
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_set_temperature(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock
) -> None:
    """Setting a target temperature sends it to the API."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    mock_device.set_temperature.assert_called_once_with(25)
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.parametrize(
    ("swing_mode", "horizontal", "vertical"),
    [
        (SWING_BOTH, True, True),
        (SWING_VERTICAL, False, True),
        (SWING_HORIZONTAL, True, False),
        (SWING_OFF, False, False),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_set_swing_mode(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    swing_mode: str,
    horizontal: bool,
    vertical: bool,
) -> None:
    """Each swing mode sets both swing axes on the device."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    mock_device.set_horizontal_swing.assert_called_once_with(horizontal)
    mock_device.set_vertical_swing.assert_called_once_with(vertical)
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.parametrize(
    ("preset_mode", "shabat"), [(PRESET_SHABAT, True), (PRESET_NONE, False)]
)
@pytest.mark.usefixtures("setup_integration")
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    preset_mode: str,
    shabat: bool,
) -> None:
    """Selecting a preset switches the Shabat mode on the device."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    mock_device.set_shabat_mode.assert_called_once_with(shabat)
    mock_api.set_state.assert_awaited_once_with(mock_device)


@pytest.mark.usefixtures("setup_integration")
async def test_command_failure_raises(hass: HomeAssistant, mock_api: Mock) -> None:
    """A failing command surfaces as a Home Assistant error."""
    mock_api.set_state = AsyncMock(side_effect=ElectraApiError("Failed to set state"))

    with pytest.raises(
        HomeAssistantError, match="Error communicating with Electra API"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_rejected_command_raises(hass: HomeAssistant, mock_api: Mock) -> None:
    """A command the API refuses surfaces as a Home Assistant error."""
    mock_api.set_state = AsyncMock(return_value={"status": 1, "data": {"res": 0}})

    with pytest.raises(
        HomeAssistantError, match="Failed to update climate.living_room"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_state_comes_from_the_telemetry_fetched_during_setup(
    hass: HomeAssistant,
) -> None:
    """The entity reports a state right after setup, without waiting for a poll."""
    state = hass.states.get(ENTITY_ID)

    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 22
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 24


@pytest.mark.usefixtures("setup_integration")
async def test_update_polls_the_cloud(
    hass: HomeAssistant,
    mock_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The coordinator asks the API for the latest telemetry on its schedule."""
    await async_advance_to_next_poll(hass, freezer)

    mock_api.get_last_telemtry.assert_awaited_once()


@pytest.mark.usefixtures("setup_integration")
async def test_update_is_skipped_right_after_a_command(
    hass: HomeAssistant,
    mock_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A command is not followed by a poll, as the API lags behind it."""
    freezer.tick(SCAN_INTERVAL_SEC - 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    # The scheduled poll now lands inside the window where the API still
    # serves the state from before the command.
    freezer.tick(3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_api.get_last_telemtry.assert_not_awaited()


async def _async_setup_two_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
    second_device: Mock,
) -> None:
    """Set up the integration with a second AC on the account."""
    mock_api.devices.append(second_device)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_every_ac_is_polled_once_per_cycle(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    second_device: Mock,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Each AC of the account is fetched once per poll, not once per entity."""
    await _async_setup_two_devices(hass, config_entry, mock_api, second_device)

    await async_advance_to_next_poll(hass, freezer)

    assert mock_api.get_last_telemtry.await_count == 2
    assert {
        call.args[0].mac for call in mock_api.get_last_telemtry.await_args_list
    } == {mock_device.mac, second_device.mac}


async def test_a_command_only_pauses_the_polls_of_that_ac(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    second_device: Mock,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Commanding one AC does not stop the other one from being polled."""
    await _async_setup_two_devices(hass, config_entry, mock_api, second_device)

    freezer.tick(SCAN_INTERVAL_SEC - 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    # The poll lands inside the window where the API still serves the state
    # from before the command, so only the other AC is fetched.
    freezer.tick(3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [
        call.args[0].mac for call in mock_api.get_last_telemtry.await_args_list
    ] == [second_device.mac]

    # Once the window has passed, both ACs are polled again.
    await async_advance_to_next_poll(hass, freezer)

    assert mock_api.get_last_telemtry.await_count == 3
    assert {
        call.args[0].mac for call in mock_api.get_last_telemtry.await_args_list
    } == {mock_device.mac, second_device.mac}


async def test_failures_are_counted_per_ac(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    second_device: Mock,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An AC that fails to answer is counted on its own."""
    await _async_setup_two_devices(hass, config_entry, mock_api, second_device)

    async def _get_telemetry(device: Mock) -> None:
        """Fail for one AC only."""
        if device is mock_device:
            raise ElectraApiError("Failed to retrieve telemetry")

    mock_api.get_last_telemtry = AsyncMock(side_effect=_get_telemetry)

    await async_advance_to_next_poll(hass, freezer)
    await async_advance_to_next_poll(hass, freezer)

    assert "Failed to get Living Room (a8032ab12345) state" in caplog.text
    assert "try #2 since last success" in caplog.text

    # The other AC answering in between does not reset the count.
    await async_advance_to_next_poll(hass, freezer)

    assert "try #3 since last success" in caplog.text
    assert "Failed to get Bedroom" not in caplog.text


@pytest.mark.parametrize(
    ("horizontal", "vertical", "expected"),
    [
        (True, True, SWING_BOTH),
        (True, False, SWING_HORIZONTAL),
        (False, True, SWING_VERTICAL),
        (False, False, SWING_OFF),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_swing_mode_reflects_the_device(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
    horizontal: bool,
    vertical: bool,
    expected: str,
) -> None:
    """The reported swing mode follows the swing state of the device."""
    mock_device.is_horizontal_swing = Mock(return_value=horizontal)
    mock_device.is_vertical_swing = Mock(return_value=vertical)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == expected


@pytest.mark.usefixtures("setup_integration")
async def test_unavailable_device_warns_once_and_recovers(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An offline AC is unavailable, and the warning is logged once per outage."""
    caplog.set_level(logging.DEBUG)
    warning = (
        "Electra AC climate.living_room (a8032ab12345) is not available,"
        " check its status in the Electra Smart mobile app"
    )
    mock_device.is_disconnected = Mock(return_value=True)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count(warning) == 1

    await async_advance_to_next_poll(hass, freezer)

    assert caplog.text.count(warning) == 1

    mock_device.is_disconnected = Mock(return_value=False)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert "is now available" in caplog.text


@pytest.mark.usefixtures("setup_integration")
async def test_update_failure_keeps_the_old_state(
    hass: HomeAssistant,
    mock_api: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed poll keeps the last known state and logs the failure."""
    mock_api.get_last_telemtry = AsyncMock(
        side_effect=ElectraApiError("Failed to retrieve telemetry")
    )

    await async_advance_to_next_poll(hass, freezer)

    assert "Failed to get Living Room (a8032ab12345) state" in caplog.text
    assert "Failed to retrieve telemetry" in caplog.text
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22


@pytest.mark.usefixtures("setup_integration")
async def test_failed_updates_are_counted_until_the_next_success(
    hass: HomeAssistant,
    mock_api: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Consecutive failures are counted, and a successful poll resets the count."""
    failure = AsyncMock(side_effect=ElectraApiError("Failed to retrieve telemetry"))
    mock_api.get_last_telemtry = failure

    await async_advance_to_next_poll(hass, freezer)
    await async_advance_to_next_poll(hass, freezer)

    assert "try #2 since last success" in caplog.text

    caplog.clear()
    mock_api.get_last_telemtry = AsyncMock()

    await async_advance_to_next_poll(hass, freezer)

    assert "Failed to get" not in caplog.text

    mock_api.get_last_telemtry = failure

    await async_advance_to_next_poll(hass, freezer)

    assert "try #1 since last success" in caplog.text
