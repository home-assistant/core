"""Test the Saunum number platform."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from pysaunum import SaunumException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_sauna_duration(
    hass: HomeAssistant,
    mock_saunum_client: MagicMock,
) -> None:
    """Test setting sauna duration."""
    entity_id = "number.saunum_leil_sauna_duration"

    # Verify initial state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "120"

    # Set new duration
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 180},
        blocking=True,
    )

    # Verify the client method was called
    mock_saunum_client.async_set_sauna_duration.assert_called_once_with(180)


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_duration(
    hass: HomeAssistant,
    mock_saunum_client: MagicMock,
) -> None:
    """Test setting fan duration."""
    entity_id = "number.saunum_leil_fan_duration"

    # Verify initial state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"

    # Set new duration
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 15},
        blocking=True,
    )

    # Verify the client method was called
    mock_saunum_client.async_set_fan_duration.assert_called_once_with(15)


@pytest.mark.usefixtures("init_integration")
async def test_set_value_failure(
    hass: HomeAssistant,
    mock_saunum_client: MagicMock,
) -> None:
    """Test error handling when setting value fails."""
    entity_id = "number.saunum_leil_sauna_duration"

    # Make the set operation fail
    mock_saunum_client.async_set_sauna_duration.side_effect = SaunumException(
        "Write error"
    )

    # Attempt to set value should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 180},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_value_while_session_active(
    hass: HomeAssistant,
    mock_saunum_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error when trying to change duration while session is active."""
    entity_id = "number.saunum_leil_sauna_duration"

    # Update mock data to have session active
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        session_active=True,
    )

    # Trigger coordinator update
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Attempt to set value should raise ServiceValidationError
    with pytest.raises(
        ServiceValidationError,
        match="Cannot change sauna duration while sauna session is active",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 180},
            blocking=True,
        )


async def test_number_with_default_duration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client: MagicMock,
) -> None:
    """Test number entities use default when device returns None."""
    # Set duration to None (device hasn't set it yet)
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        sauna_duration=None,
        fan_duration=None,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should show default values
    sauna_duration_state = hass.states.get("number.saunum_leil_sauna_duration")
    assert sauna_duration_state is not None
    assert sauna_duration_state.state == "120"  # DEFAULT_DURATION_MIN

    fan_duration_state = hass.states.get("number.saunum_leil_fan_duration")
    assert fan_duration_state is not None
    assert fan_duration_state.state == "15"  # DEFAULT_FAN_DURATION_MIN


async def test_number_with_valid_duration_from_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client: MagicMock,
) -> None:
    """Test number entities use actual values from device when valid."""
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        sauna_duration=90,
        fan_duration=20,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should show actual device values
    sauna_duration_state = hass.states.get("number.saunum_leil_sauna_duration")
    assert sauna_duration_state is not None
    assert sauna_duration_state.state == "90"

    fan_duration_state = hass.states.get("number.saunum_leil_fan_duration")
    assert fan_duration_state is not None
    assert fan_duration_state.state == "20"
