"""Velbus climate platform tests."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.CLIMATE]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_set_target_temperature(
    hass: HomeAssistant,
    mock_temperature: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the target temperature climate action."""
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.temperature", ATTR_TEMPERATURE: 29},
        blocking=True,
    )
    mock_temperature.set_temp.assert_called_once_with(29)


@pytest.mark.parametrize(
    ("set_mode", "expected_mode"),
    [
        (PRESET_AWAY, "night"),
        (PRESET_COMFORT, "comfort"),
        (PRESET_ECO, "safe"),
        (PRESET_HOME, "day"),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_temperature: AsyncMock,
    config_entry: MockConfigEntry,
    set_mode: str,
    expected_mode: str,
) -> None:
    """Test the preset mode climate action."""
    await init_integration(hass, config_entry)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.temperature", ATTR_PRESET_MODE: set_mode},
        blocking=True,
    )
    mock_temperature.set_preset.assert_called_once_with(expected_mode)


@pytest.mark.parametrize(
    ("set_mode"),
    [
        ("heat"),
        ("cool"),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_temperature: AsyncMock,
    config_entry: MockConfigEntry,
    set_mode: str,
) -> None:
    """Test the hvac mode climate action."""
    await init_integration(hass, config_entry)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.temperature", ATTR_HVAC_MODE: set_mode},
        blocking=True,
    )
    mock_temperature.set_mode.assert_called_once_with(set_mode)


async def test_set_hvac_mode_invalid(
    hass: HomeAssistant,
    mock_temperature: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the hvac mode climate action with an invalid mode."""
    await init_integration(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.temperature", ATTR_HVAC_MODE: "auto"},
            blocking=True,
        )
    mock_temperature.set_mode.assert_not_called()
