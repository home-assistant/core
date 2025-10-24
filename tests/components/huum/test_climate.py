"""Tests for the Huum climate entity."""

from unittest.mock import AsyncMock

from huum.const import SaunaStatus
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.huum.const import (
    CONFIG_DEFAULT_MAX_TEMP,
    CONFIG_DEFAULT_MIN_TEMP,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.huum_sauna"


async def test_climate_entity(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    mock_huum.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT

    mock_huum.turn_on.assert_called_once()


async def test_set_temperature(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    mock_huum.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 60,
        },
        blocking=True,
    )

    mock_huum.turn_on.assert_called_once_with(60)


async def test_temperature_range(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the temperature range."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # API response.
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == 40
    assert state.attributes["max_temp"] == 110

    # Empty/unconfigured API response should return default values.
    mock_huum.sauna_config.min_temp = 0
    mock_huum.sauna_config.max_temp = 0

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == CONFIG_DEFAULT_MIN_TEMP
    assert state.attributes["max_temp"] == CONFIG_DEFAULT_MAX_TEMP

    # Custom configured API response.
    mock_huum.sauna_config.min_temp = 50
    mock_huum.sauna_config.max_temp = 80

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == 50
    assert state.attributes["max_temp"] == 80
