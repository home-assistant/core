"""Tests for the Zonneplan binary sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyzonneplan import ZonneplanConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan import Platform
from homeassistant.components.zonneplan.coordinator import BATTERY_UPDATE_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

LOW_PRICE_ENTITY_ID = "binary_sensor.zonneplan_electricity_price_low"
GRID_CONGESTION_ENTITY_ID = "binary_sensor.thuisbatterij_grid_congestion"


@pytest.mark.parametrize(
    "frozen_time",
    [
        pytest.param("2026-08-29T08:30:00+00:00", id="in_low_price_block"),
        pytest.param("2026-08-29T17:30:00+00:00", id="outside_low_price_block"),
        pytest.param("2026-08-30T22:30:00+00:00", id="no_prices_today"),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    frozen_time: str,
) -> None:
    """Test the binary sensor entities."""
    freezer.move_to(frozen_time)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_battery_binary_sensor_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the battery binary sensors become unavailable when an update fails."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get(GRID_CONGESTION_ENTITY_ID))
    assert state.state == STATE_ON

    mock_zonneplan_client.async_get_battery.side_effect = ZonneplanConnectionError(
        "boom"
    )
    freezer.tick(BATTERY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(GRID_CONGESTION_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
