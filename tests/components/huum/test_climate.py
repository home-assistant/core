"""Tests for the Huum climate entity."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from huum.const import SaunaStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
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

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.huum_sauna"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("init_integration")
async def test_climate_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test setting HVAC mode."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT

    mock_huum_client.turn_on.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test setting the temperature."""
    mock_huum_client.status.return_value.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 60,
        },
        blocking=True,
    )

    mock_huum_client.turn_on.assert_awaited_once_with(60)


@pytest.mark.usefixtures("init_integration")
async def test_temperature_range(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the temperature range."""
    # API response.
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == 40
    assert state.attributes["max_temp"] == 110

    # Empty/unconfigured API response should return default values.
    mock_huum_client.status.return_value.sauna_config.min_temp = 0
    mock_huum_client.status.return_value.sauna_config.max_temp = 0

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == CONFIG_DEFAULT_MIN_TEMP
    assert state.attributes["max_temp"] == CONFIG_DEFAULT_MAX_TEMP

    # Custom configured API response.
    mock_huum_client.status.return_value.sauna_config.min_temp = 50
    mock_huum_client.status.return_value.sauna_config.max_temp = 80

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == 50
    assert state.attributes["max_temp"] == 80
