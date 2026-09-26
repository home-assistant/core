"""Tests for the Zonneplan binary sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

LOW_PRICE_ENTITY_ID = "binary_sensor.zonneplan_electricity_price_low"


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
