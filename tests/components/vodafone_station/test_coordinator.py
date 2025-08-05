"""Define tests for the Vodafone Station coordinator."""

import logging
from unittest.mock import AsyncMock

from aiovodafone import VodafoneStationDevice
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import DEVICE_1_HOST, DEVICE_1_MAC, DEVICE_2_HOST, DEVICE_2_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_device_cleanup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Device cleanup on coordinator update."""

    caplog.set_level(logging.DEBUG)
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_1_MAC)},
        name=DEVICE_1_HOST,
    )
    assert device is not None

    device_tracker = f"device_tracker.{DEVICE_1_HOST}"

    assert hass.states.get(device_tracker)

    mock_vodafone_station_router.get_devices_data.return_value = {
        DEVICE_2_MAC: VodafoneStationDevice(
            connected=True,
            connection_type="lan",
            ip_address="192.168.1.11",
            name=DEVICE_2_HOST,
            mac=DEVICE_2_MAC,
            type="desktop",
            wifi="",
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(device_tracker) is None
    assert f"Skipping entity {DEVICE_2_HOST}" in caplog.text

    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_1_MAC)}) is None
    )
    assert f"Removing device: {DEVICE_1_HOST}" in caplog.text
