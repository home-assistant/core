"""Test the Imeon Inverter sensors."""

from unittest.mock import MagicMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.components.imeon_inverter.coordinator import INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Imeon Inverter sensors."""
    with patch("homeassistant.components.imeon_inverter.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        ClientError,
        ValueError,
    ],
)
@pytest.mark.asyncio
async def test_sensor_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imeon_inverter: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that sensor becomes unavailable when update raises an error."""
    entity_registry = er.async_get(hass)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{TEST_SERIAL}_battery_power",
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_imeon_inverter.update.side_effect = exception

    freezer.tick(INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_imeon_inverter.update.side_effect = None

    freezer.tick(INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
