"""Tests for Atomberg water purifier entities."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE as TIME_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

DEVICE_ID = "a4cf12aa0001"
MODE = "select.kitchen_water_purifier_purification_mode"
FALLBACK = "select.kitchen_water_purifier_fallback_mode"
THRESHOLD = "number.kitchen_water_purifier_tds_threshold"
IDLE_SLEEP = "switch.kitchen_water_purifier_idle_display_sleep"
SLEEP_WINDOW = "switch.kitchen_water_purifier_sleep_window"
WINDOW_START = "time.kitchen_water_purifier_sleep_window_start"
WINDOW_END = "time.kitchen_water_purifier_sleep_window_end"
SECONDS_PER_DAY = 86400


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        (MODE, "adaptive"),
        (FALLBACK, "ro_only"),
        (THRESHOLD, "150"),
        (IDLE_SLEEP, STATE_ON),
        (SLEEP_WINDOW, STATE_OFF),
        (WINDOW_START, STATE_UNKNOWN),
        (WINDOW_END, STATE_UNKNOWN),
        ("sensor.kitchen_water_purifier_input_tds", "240"),
        ("sensor.kitchen_water_purifier_tank_tds", "35"),
        ("sensor.kitchen_water_purifier_last_reported", "2026-11-03T10:00:00+00:00"),
        ("binary_sensor.kitchen_water_purifier_filter_choked", STATE_OFF),
        ("binary_sensor.kitchen_water_purifier_valve_fault", STATE_ON),
        ("binary_sensor.kitchen_water_purifier_system_fault", STATE_ON),
        ("binary_sensor.kitchen_water_purifier_no_water", STATE_ON),
        ("binary_sensor.kitchen_water_purifier_tank_full", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected: str,
) -> None:
    """Test water purifier state mapping."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected


@pytest.mark.parametrize(
    ("entity_id", "option", "command"),
    [
        (MODE, "vacation", {"mode": 10}),
        (MODE, "tastetune_75_125", {"mode": 3}),
        (FALLBACK, "tastetune_100_150", {"fallback_mode": 4}),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    option: str,
    command: dict,
) -> None:
    """Test mode selects send the numeric mode and update state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(DEVICE_ID, command)
    assert hass.states.get(entity_id).state == option


async def test_set_tds_threshold(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting the TDS threshold."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SET_VALUE,
        {ATTR_ENTITY_ID: THRESHOLD, ATTR_VALUE: 200},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(
        DEVICE_ID, {"tds_threshold": 200}
    )
    assert hass.states.get(THRESHOLD).state == "200"


@pytest.mark.parametrize(
    ("service", "value", "state"),
    [(SERVICE_TURN_OFF, 0, STATE_OFF), (SERVICE_TURN_ON, 1, STATE_ON)],
)
async def test_idle_sleep_switch(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    value: int,
    state: str,
) -> None:
    """Test the idle display sleep switch sends 0 or 1."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: IDLE_SLEEP}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(
        DEVICE_ID, {"idle_sleep": value}
    )
    assert hass.states.get(IDLE_SLEEP).state == state


async def test_sleep_window_needs_times_first(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test enabling the window before setting both times is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="Set the sleep window"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SLEEP_WINDOW},
            blocking=True,
        )

    mock_client.async_send_command.assert_not_awaited()


async def test_sleep_window_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test times are held until the window is enabled, then sent together."""
    await hass.config.async_set_time_zone("UTC")
    await setup_integration(hass, mock_config_entry)

    for entity_id, value in ((WINDOW_START, "22:00:00"), (WINDOW_END, "06:00:00")):
        await hass.services.async_call(
            TIME_DOMAIN,
            TIME_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: value},
            blocking=True,
        )
    mock_client.async_send_command.assert_not_awaited()
    assert hass.states.get(WINDOW_START).state == "22:00:00"
    assert hass.states.get(WINDOW_END).state == "06:00:00"

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SLEEP_WINDOW}, blocking=True
    )

    device_id, command = mock_client.async_send_command.await_args.args
    assert device_id == DEVICE_ID
    assert command["sleep_mode"] == 1
    assert command["start_utc"] % SECONDS_PER_DAY == 22 * 3600
    assert command["stop_utc"] % SECONDS_PER_DAY == 6 * 3600
    assert hass.states.get(SLEEP_WINDOW).state == STATE_ON


async def test_sleep_window_off(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test disabling the window sends sleep_mode 0 only."""
    mock_client.async_get_states.return_value[DEVICE_ID]["sleep_mode"] = 1

    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SLEEP_WINDOW}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(
        DEVICE_ID, {"sleep_mode": 0}
    )


async def test_time_change_while_window_on_is_sent(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test changing a time while the window is on updates the device at once."""
    await hass.config.async_set_time_zone("UTC")
    state = mock_client.async_get_states.return_value[DEVICE_ID]
    state.update({"sleep_mode": 1, "start_utc": 79200, "stop_utc": 21600})
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        TIME_SET_VALUE,
        {ATTR_ENTITY_ID: WINDOW_END, ATTR_TIME: "07:00:00"},
        blocking=True,
    )

    command = mock_client.async_send_command.await_args.args[1]
    assert command["sleep_mode"] == 1
    assert command["start_utc"] == 79200
    assert command["stop_utc"] % SECONDS_PER_DAY == 7 * 3600
