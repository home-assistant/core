"""Tests for Zentraly thermostat states, services and refreshes."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import timedelta
from unittest.mock import MagicMock, call

import pytest
from zentraly import ClimateCapability, ClimateOperationMode, ZentralyConnectionError

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    PRESET_AWAY,
    PRESET_NONE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import ENTITY_ID

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        pytest.param(HVACMode.OFF, ClimateOperationMode.OFF, id="off"),
        pytest.param(HVACMode.HEAT, ClimateOperationMode.MANUAL, id="heat"),
        pytest.param(HVACMode.AUTO, ClimateOperationMode.AUTO, id="auto"),
    ],
)
async def test_hvac_mode(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    mode: HVACMode,
    operation: ClimateOperationMode,
) -> None:
    """Translate Home Assistant mode actions into device operations."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == mode
    mock_climate_api.async_set_operation_mode.assert_awaited_once_with(operation)


@pytest.mark.parametrize(
    ("success", "expected", "expectation"),
    [
        pytest.param(True, 22.0, nullcontext(), id="success"),
        pytest.param(False, 21.0, pytest.raises(HomeAssistantError), id="failure"),
    ],
)
async def test_temperature_write(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    success: bool,
    expected: float,
    expectation: AbstractContextManager,
) -> None:
    """A failed service action preserves the last reported setpoint."""
    mock_climate_api.async_set_target_temperature.return_value = success
    with expectation:
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == expected
    mock_climate_api.async_set_target_temperature.assert_awaited_once_with(22.0)


async def test_away_report(hass: HomeAssistant, mock_climate_api: MagicMock) -> None:
    """Library reports update the registered entity's Away target and heat demand."""
    mock_climate_api.add_state_listener.call_args.args[0](
        {
            ClimateCapability.LOCAL_TEMPERATURE: 19.0,
            ClimateCapability.TARGET_TEMPERATURE: 17.0,
            ClimateCapability.OPERATION_MODE: ClimateOperationMode.AWAY,
            ClimateCapability.HEAT_DEMAND: True,
            ClimateCapability.HUMIDITY: 52.0,
        }
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19.0
    assert state.attributes[ATTR_TEMPERATURE] == 17.0
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 52.0
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING


async def test_missing_readings_clear_previous_values(
    hass: HomeAssistant, mock_climate_api: MagicMock
) -> None:
    """Missing readings become unknown without marking the device disconnected."""
    mock_climate_api.async_get_current_temperature.return_value = None
    mock_climate_api.async_get_target_temperature.return_value = None
    mock_climate_api.async_get_operation_mode.return_value = None
    mock_climate_api.async_get_humidity.return_value = None
    mock_climate_api.async_get_heat_demand.return_value = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert ATTR_CURRENT_HUMIDITY not in state.attributes
    assert ATTR_HVAC_ACTION not in state.attributes


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        pytest.param(HVACMode.AUTO, ClimateOperationMode.AUTO, id="auto"),
        pytest.param(HVACMode.OFF, ClimateOperationMode.OFF, id="off"),
        pytest.param(HVACMode.HEAT, ClimateOperationMode.MANUAL, id="heat"),
    ],
)
async def test_temperature_with_explicit_mode(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    mode: HVACMode,
    operation: ClimateOperationMode,
) -> None:
    """An explicit mode is written after the setpoint's manual-mode side effect."""
    writes = MagicMock()
    writes.attach_mock(mock_climate_api.async_set_target_temperature, "temperature")
    writes.attach_mock(mock_climate_api.async_set_operation_mode, "mode")
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0, ATTR_HVAC_MODE: mode},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.state == mode
    assert writes.mock_calls == [call.temperature(22.0), call.mode(operation)]


@pytest.mark.parametrize(
    ("initial", "requested", "operation", "success", "expected", "expectation"),
    [
        pytest.param(
            ClimateOperationMode.MANUAL,
            PRESET_AWAY,
            ClimateOperationMode.AWAY,
            True,
            PRESET_AWAY,
            nullcontext(),
            id="enter-away",
        ),
        pytest.param(
            ClimateOperationMode.MANUAL,
            PRESET_AWAY,
            ClimateOperationMode.AWAY,
            False,
            PRESET_NONE,
            pytest.raises(HomeAssistantError),
            id="enter-failure",
        ),
        pytest.param(
            ClimateOperationMode.AWAY,
            PRESET_NONE,
            ClimateOperationMode.MANUAL,
            True,
            PRESET_NONE,
            nullcontext(),
            id="exit-away",
        ),
        pytest.param(
            ClimateOperationMode.AWAY,
            PRESET_NONE,
            ClimateOperationMode.MANUAL,
            False,
            PRESET_AWAY,
            pytest.raises(HomeAssistantError),
            id="exit-failure",
        ),
    ],
)
async def test_preset_write(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    initial: ClimateOperationMode,
    requested: str,
    operation: ClimateOperationMode,
    success: bool,
    expected: str,
    expectation: AbstractContextManager,
) -> None:
    """Only confirmed preset actions update the reported thermostat state."""
    mock_climate_api.add_state_listener.call_args.args[0](
        {ClimateCapability.OPERATION_MODE: initial}
    )
    mock_climate_api.async_set_operation_mode.return_value = success
    with expectation:
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: requested},
            blocking=True,
        )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == expected
    mock_climate_api.async_set_operation_mode.assert_awaited_once_with(operation)


async def test_failed_hvac_mode(
    hass: HomeAssistant, mock_climate_api: MagicMock
) -> None:
    """A rejected mode write exposes a translated HA error without changing state."""
    mock_climate_api.async_set_operation_mode.return_value = False
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
    assert exc.value.translation_key == "action_failed"
    assert exc.value.translation_domain == "zentraly"
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


async def test_periodic_refresh_during_reconnect(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    connection_state: Callable[[bool], None],
) -> None:
    """A periodic refresh shares HA's update guard with a reconnect refresh."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def read() -> float:
        started.set()
        await release.wait()
        return 20.0

    mock_climate_api.async_get_current_temperature.reset_mock()
    mock_climate_api.async_get_current_temperature.side_effect = read
    connection_state(False)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    connection_state(True)
    await started.wait()
    now = dt_util.utcnow()
    try:
        async_fire_time_changed(hass, now + timedelta(minutes=5))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_climate_api.async_get_current_temperature.assert_awaited_once_with()
    finally:
        release.set()
        await hass.async_block_till_done()
    async_fire_time_changed(hass, now + timedelta(minutes=10))
    await hass.async_block_till_done()
    assert mock_climate_api.async_get_current_temperature.await_count == 2
    assert hass.states.get(ENTITY_ID).attributes[ATTR_CURRENT_TEMPERATURE] == 20.0


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ZentralyConnectionError, id="failure"),
        pytest.param(asyncio.CancelledError, id="cancelled"),
    ],
)
async def test_failed_refresh_cleans_up_reads(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    error: type[BaseException],
    connection_state: Callable[[bool], None],
) -> None:
    """Failed or cancelled reads clean up their siblings and allow a later refresh."""
    started = asyncio.Event()
    cleaned_up = asyncio.Event()
    release = asyncio.Event()

    async def failing_read() -> float:
        await started.wait()
        raise error()

    async def pending_read() -> float:
        started.set()
        try:
            await release.wait()
        finally:
            await asyncio.sleep(0)
            cleaned_up.set()
        return 21.0

    mock_climate_api.async_get_current_temperature.side_effect = failing_read
    mock_climate_api.async_get_target_temperature.side_effect = pending_read
    try:
        connection_state(True)
        await hass.async_block_till_done()
        assert cleaned_up.is_set()
    finally:
        release.set()
        await hass.async_block_till_done()
    mock_climate_api.async_get_current_temperature.side_effect = None
    mock_climate_api.async_get_target_temperature.side_effect = None
    connection_state(True)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 21.0


async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    mock_climate_api: MagicMock,
) -> None:
    """Unload disconnects the client, removes listeners and stops climate polling."""
    reads = mock_climate_api.async_get_current_temperature.await_count
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.async_disconnect.assert_awaited_once_with()
    mock_climate_api.add_state_listener.return_value.assert_called_once_with()
    assert mock_api.add_connection_state_listener.return_value.call_count == 2
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert mock_climate_api.async_get_current_temperature.await_count == reads
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_action_waits_for_refresh(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    connection_state: Callable[[bool], None],
) -> None:
    """A pending refresh cannot overwrite the state from a subsequent action."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def read() -> float:
        started.set()
        await release.wait()
        return 19.0

    mock_climate_api.async_get_current_temperature.side_effect = read
    connection_state(True)
    await started.wait()
    action = hass.async_create_task(
        hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )
    )
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_climate_api.async_set_target_temperature.assert_not_awaited()
        assert not action.done()
    finally:
        release.set()
        await action
        await hass.async_block_till_done()
    mock_climate_api.async_set_target_temperature.assert_awaited_once_with(22.0)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22.0
