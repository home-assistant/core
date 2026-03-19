"""Tests for the Roth Touchline SL climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import make_mock_module, make_mock_zone

from tests.common import MockConfigEntry

ENTITY_ID = "climate.zone_1"


async def test_climate_zone_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
) -> None:
    """Test that the climate entity is available when zone has no alarm."""
    zone = make_mock_zone(alarm=None)
    module = make_mock_module([zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT


@pytest.mark.parametrize("alarm", ["no_communication", "sensor_damaged"])
async def test_climate_zone_unavailable_on_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
    alarm: str,
) -> None:
    """Test that the climate entity is unavailable when zone reports an alarm state."""
    zone = make_mock_zone(alarm=alarm)
    module = make_mock_module([zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
