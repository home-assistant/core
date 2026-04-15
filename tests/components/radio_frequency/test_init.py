"""Tests for the Radio Frequency integration setup."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from rf_protocols import ModulationType

from homeassistant.components.radio_frequency import (
    DATA_COMPONENT,
    DOMAIN,
    async_get_transmitters,
    async_send_command,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    MockRadioFrequencyCommand,
    MockRadioFrequencyEntity,
    MockRadioFrequencyEntityWithRanges,
)

from tests.common import mock_restore_cache


async def test_get_transmitters_component_not_loaded(hass: HomeAssistant) -> None:
    """Test getting transmitters raises when the component is not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        async_get_transmitters(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("init_integration")
async def test_get_transmitters_no_entities(hass: HomeAssistant) -> None:
    """Test getting transmitters raises when none are registered."""
    with pytest.raises(
        HomeAssistantError,
        match="No Radio Frequency transmitters available",
    ):
        async_get_transmitters(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("init_integration")
async def test_get_transmitters_no_frequency_ranges(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test transmitter with no frequency ranges matches any frequency."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity])

    result = async_get_transmitters(hass, 433_920_000, ModulationType.OOK)
    assert result == [mock_rf_entity.entity_id]

    result = async_get_transmitters(hass, 868_000_000, ModulationType.OOK)
    assert result == [mock_rf_entity.entity_id]


@pytest.mark.usefixtures("init_integration")
async def test_get_transmitters_with_frequency_ranges(
    hass: HomeAssistant,
    mock_rf_entity_with_ranges: MockRadioFrequencyEntityWithRanges,
) -> None:
    """Test transmitter with frequency ranges filters correctly."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity_with_ranges])

    # 433.92 MHz is within 433-434 MHz range
    result = async_get_transmitters(hass, 433_920_000, ModulationType.OOK)
    assert result == [mock_rf_entity_with_ranges.entity_id]

    # 868 MHz is outside the range
    result = async_get_transmitters(hass, 868_000_000, ModulationType.OOK)
    assert result == []


@pytest.mark.usefixtures("init_integration")
async def test_rf_entity_initial_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test radio frequency entity has no state before any command is sent."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity])

    state = hass.states.get("radio_frequency.test_rf_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_success(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity])

    now = dt_util.utcnow()
    freezer.move_to(now)

    command = MockRadioFrequencyCommand(frequency=433_920_000)
    await async_send_command(hass, mock_rf_entity.entity_id, command)

    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0] is command

    state = hass.states.get("radio_frequency.test_rf_transmitter")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_error_does_not_update_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test that state is not updated when async_send_command raises an error."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity])

    state = hass.states.get("radio_frequency.test_rf_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    command = MockRadioFrequencyCommand(frequency=433_920_000)

    mock_rf_entity.async_send_command = AsyncMock(
        side_effect=HomeAssistantError("Transmission failed")
    )

    with pytest.raises(HomeAssistantError, match="Transmission failed"):
        await async_send_command(hass, mock_rf_entity.entity_id, command)

    state = hass.states.get("radio_frequency.test_rf_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_entity_not_found(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when entity not found."""
    command = MockRadioFrequencyCommand(frequency=433_920_000)

    with pytest.raises(
        HomeAssistantError,
        match="Radio Frequency entity `radio_frequency.nonexistent_entity` not found",
    ):
        await async_send_command(hass, "radio_frequency.nonexistent_entity", command)


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    command = MockRadioFrequencyCommand(frequency=433_920_000)

    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        await async_send_command(hass, "radio_frequency.some_entity", command)


@pytest.mark.parametrize(
    ("restored_value", "expected_state"),
    [
        ("2026-01-01T12:00:00.000+00:00", "2026-01-01T12:00:00.000+00:00"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_rf_entity_state_restore(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    restored_value: str,
    expected_state: str,
) -> None:
    """Test radio frequency entity state restore."""
    mock_restore_cache(
        hass, [State("radio_frequency.test_rf_transmitter", restored_value)]
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_rf_entity])

    state = hass.states.get("radio_frequency.test_rf_transmitter")
    assert state is not None
    assert state.state == expected_state
