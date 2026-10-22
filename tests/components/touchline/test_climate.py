"""Tests for the Touchline climate platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


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
    mock_pytouchline: MagicMock,
) -> None:
    """Test setting the temperature."""
    await hass.services.async_call(
        "climate",
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.zone_1", ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    mock_pytouchline.set_target_temperature.assert_called_once_with(22.0)


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_error(
    hass: HomeAssistant,
    mock_pytouchline: MagicMock,
) -> None:
    """Test error handling when setting the temperature."""
    # Simulate an error when setting the temperature
    mock_pytouchline.set_target_temperature.side_effect = ConnectionError(
        "Unexpected backend explosion"
    )

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the temperature"
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.zone_1", ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_pytouchline: MagicMock,
) -> None:
    """Test setting the preset mode."""
    await hass.services.async_call(
        "climate",
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.zone_1", ATTR_PRESET_MODE: "sleep"},
        blocking=True,
    )

    mock_pytouchline.set_operation_mode.assert_called_once_with(1)
    mock_pytouchline.set_week_program.assert_called_once_with(0)


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_error(
    hass: HomeAssistant,
    mock_pytouchline: MagicMock,
) -> None:
    """Test error handling when setting the preset mode."""
    mock_pytouchline.set_operation_mode.side_effect = ConnectionError(
        "Unexpected backend explosion"
    )

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the preset mode"
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.zone_1", ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )
