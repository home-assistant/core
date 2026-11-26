"""Tests for the Touchline climate platform."""

from dataclasses import replace
import logging
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytouchline_extended import TouchlineConnectionError, TouchlineResponseError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.touchline.coordinator import UPDATE_INTERVAL
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ROOM_STATUS, make_state

ENTITY_ID = "climate.zone_1"
COORDINATOR_LOGGER = "homeassistant.components.touchline.coordinator"


@pytest.mark.usefixtures("init_integration")
async def test_climate_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Touchline climate entities match the snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test setting the temperature."""
    await hass.services.async_call(
        "climate",
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.TEMPERATURE: 22.0,
        },
        blocking=True,
    )

    mock_touchline_controller.set_room_target_temperature_async.assert_called_once_with(
        0, 22.0
    )
    assert mock_touchline_controller.fetch_async.call_count == 2


@pytest.mark.parametrize(
    ("return_value", "side_effect"),
    [
        pytest.param(False, None, id="returns-false"),
        pytest.param(
            None,
            TouchlineConnectionError("Unexpected backend explosion"),
            id="connection-error",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_error(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    return_value: bool | None,
    side_effect: Exception | None,
) -> None:
    """Test error handling when setting the temperature."""
    mock_touchline_controller.set_room_target_temperature_async.return_value = (
        return_value
    )
    mock_touchline_controller.set_room_target_temperature_async.side_effect = (
        side_effect
    )

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the temperature"
    ):
        await hass.services.async_call(
            "climate",
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                ClimateServiceArgument.TEMPERATURE: 22.0,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test setting the preset mode."""
    await hass.services.async_call(
        "climate",
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.PRESET_MODE: "sleep",
        },
        blocking=True,
    )

    mock_touchline_controller.set_room_operation_mode_async.assert_called_once_with(
        0, 1
    )
    mock_touchline_controller.set_room_week_program_async.assert_called_once_with(0, 0)
    assert mock_touchline_controller.fetch_async.call_count == 2


@pytest.mark.parametrize(
    ("operation_mode_result", "week_program_result", "side_effect"),
    [
        pytest.param(False, True, None, id="operation-mode-returns-false"),
        pytest.param(True, False, None, id="week-program-returns-false"),
        pytest.param(
            None,
            None,
            TouchlineConnectionError("Unexpected backend explosion"),
            id="connection-error",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_error(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    operation_mode_result: bool | None,
    week_program_result: bool | None,
    side_effect: Exception | None,
) -> None:
    """Test error handling when setting the preset mode."""
    mock_touchline_controller.set_room_operation_mode_async.return_value = (
        operation_mode_result
    )
    mock_touchline_controller.set_room_week_program_async.return_value = (
        week_program_result
    )
    mock_touchline_controller.set_room_operation_mode_async.side_effect = side_effect

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the preset mode"
    ):
        await hass.services.async_call(
            "climate",
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                ClimateServiceArgument.PRESET_MODE: "sleep",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test setting the only supported HVAC mode does not write to the controller."""
    await hass.services.async_call(
        "climate",
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
    mock_touchline_controller.set_room_operation_mode_async.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "log_level"),
    [
        pytest.param(TouchlineConnectionError, logging.INFO, id="unreachable"),
        pytest.param(TouchlineResponseError, logging.ERROR, id="invalid-response"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_unavailable_when_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_touchline_controller: MagicMock,
    side_effect: type[Exception],
    log_level: int,
) -> None:
    """Test the entity becomes unavailable, logs once and recovers."""
    caplog.set_level(logging.INFO, logger=COORDINATOR_LOGGER)
    mock_touchline_controller.fetch_async.side_effect = side_effect

    for _ in range(2):
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # One fetch during setup and two failed polls.
    assert mock_touchline_controller.fetch_async.call_count == 3
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert [
        record.levelno
        for record in caplog.records
        if record.name == COORDINATOR_LOGGER and record.levelno >= logging.INFO
    ] == [log_level]

    mock_touchline_controller.fetch_async.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
    assert "Fetching touchline data recovered" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_when_thermostat_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test the entity becomes unavailable when the controller stops reporting it."""
    mock_touchline_controller.fetch_async.return_value = make_state()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_touchline_controller.fetch_async.return_value = make_state(ROOM_STATUS)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


async def test_thermostat_identity_after_reindexing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test entities follow their thermostat by ID when the controller reindexes."""
    second_room = replace(
        ROOM_STATUS,
        index=1,
        device_id=5,
        unique_id="1-5",
        name="Zone 2",
        temperature=19.0,
        target_temperature=20.0,
    )
    mock_touchline_controller.fetch_async.return_value = make_state(
        ROOM_STATUS, second_room
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The first thermostat is unpaired and the second one moves to another slot.
    mock_touchline_controller.fetch_async.return_value = make_state(
        replace(second_room, index=2)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    state = hass.states.get("climate.zone_2")
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    await hass.services.async_call(
        "climate",
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.zone_2",
            ClimateServiceArgument.TEMPERATURE: 21.0,
        },
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: "climate.zone_2",
            ClimateServiceArgument.PRESET_MODE: "sleep",
        },
        blocking=True,
    )

    mock_touchline_controller.set_room_target_temperature_async.assert_called_once_with(
        2, 21.0
    )
    mock_touchline_controller.set_room_operation_mode_async.assert_called_once_with(
        2, 1
    )
    mock_touchline_controller.set_room_week_program_async.assert_called_once_with(2, 0)
