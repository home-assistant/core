"""Test the Mitsubishi WF-RAC climate platform."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.living_room"


async def test_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The climate entity reflects the state the module reported."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_state_from_the_module(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The captured frame has the unit off, in cool, set to 22 degrees."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.attributes["current_temperature"] == 24.7


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 21.0}),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "auto"}),
        (SERVICE_SET_SWING_MODE, {ATTR_SWING_MODE: "highest"}),
    ],
)
async def test_commands_reach_the_module(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    service: str,
    data: dict,
) -> None:
    """Every setter ends up as one frame sent to the airco."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


async def test_temperature_outside_the_units_range_is_refused(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Refuse a setpoint the unit itself does not offer.

    Asking past the reported range is an error, not a value quietly clamped
    behind the user's back.
    """
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 40.0},
            blocking=True,
        )


async def test_set_temperature_without_a_single_setpoint(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A range call has no single setpoint to send.

    The unit takes one target temperature, so the high/low pair the climate
    schema also accepts is refused rather than silently reduced to one of the
    two.
    """
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "target_temp_low": 20.0,
                "target_temp_high": 24.0,
            },
            blocking=True,
        )


async def test_preset_away_switches_the_unit_to_home_leave(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Hand the away preset to the unit's own Home Leave mode.

    It is the unit's mode rather than a setpoint we invent, so it only means
    something while the unit is cooling or heating.

    The running state is set on the coordinator rather than driven through a
    command: the mocked module echoes one fixed status frame back, so a write
    would not change what the next read reports.
    """
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


async def test_preset_away_needs_a_direction(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """While the unit is off there is no cool-or-heat for Home Leave to mean."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )


async def test_turn_on_and_off(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Turning off keeps the mode, so turning on again returns to it."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_repository.send_airco_command.assert_awaited()

    mock_repository.send_airco_command.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_repository.send_airco_command.assert_awaited()


async def test_horizontal_swing(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The left/right louver is its own axis on this hardware."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: "left_left"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


async def test_commands_close_together_become_one_frame(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Coalesce commands issued together into one frame.

    The module takes one connection at a time and wants a second between
    requests, so two changes made at once have to leave as a single write.
    """
    mock_repository.send_airco_command.reset_mock()

    await asyncio.gather(
        hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        ),
        hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        ),
    )
    await hass.async_block_till_done()

    assert mock_repository.send_airco_command.await_count == 1
