"""Tests for the Meater integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meater.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import PROBE_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_meater_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, PROBE_ID)})
    assert device_entry is not None
    assert device_entry == snapshot
