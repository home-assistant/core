"""Test the Tractive switch platform."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.tractive.const import TRACKER_SWITCH_STATUS_UPDATED
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)
        async_dispatcher_send(
            hass,
            f"{TRACKER_SWITCH_STATUS_UPDATED}-device_id_123",
            {
                "buzzer": True,
                "led": False,
                "live_tracking": True,
            },
        )
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
