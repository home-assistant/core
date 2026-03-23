"""Tests for the Roth Touchline SL climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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


async def test_zones_with_same_id_across_modules_get_distinct_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
) -> None:
    """Test that identical zone IDs on different modules produce separate devices."""
    zone_a = make_mock_zone(zone_id=1, name="Zone 1")
    zone_b = make_mock_zone(zone_id=1, name="Zone 1")

    module_a = make_mock_module([zone_a])
    module_a.id = "module-aaa"
    module_b = make_mock_module([zone_b])
    module_b.id = "module-bbb"

    mock_touchlinesl_client.modules = AsyncMock(return_value=[module_a, module_b])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    device_a = registry.async_get_device(identifiers={("touchline_sl", "module-aaa-1")})
    device_b = registry.async_get_device(identifiers={("touchline_sl", "module-bbb-1")})

    assert device_a is not None
    assert device_b is not None
    assert device_a.id != device_b.id
