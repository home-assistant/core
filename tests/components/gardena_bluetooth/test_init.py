"""Test the Gardena Bluetooth setup."""

import asyncio
from datetime import timedelta
from unittest.mock import Mock, patch

from gardena_bluetooth.const import Battery
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gardena_bluetooth import DeviceUnavailable
from homeassistant.components.gardena_bluetooth.const import DOMAIN
from homeassistant.components.gardena_bluetooth.util import (
    async_get_product_type as original_get_product_type,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import utcnow

from . import MISSING_MANUFACTURER_DATA_SERVICE_INFO, WATER_TIMER_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_read_char_raw[Battery.battery_level.uuid] = Battery.battery_level.encode(100)
    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id) is True

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, WATER_TIMER_SERVICE_INFO.address)}
    )
    assert device == snapshot


async def test_setup_delayed_product(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_entry: MockConfigEntry,
    mock_read_char_raw: dict[str, bytes],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_read_char_raw[Battery.battery_level.uuid] = Battery.battery_level.encode(100)

    mock_entry.add_to_hass(hass)

    event = asyncio.Event()

    async def _get_product_type(*args, **kwargs):
        event.set()
        return await original_get_product_type(*args, **kwargs)

    with patch(
        "homeassistant.components.gardena_bluetooth.async_get_product_type",
        wraps=_get_product_type,
    ):
        async with asyncio.TaskGroup() as tg:
            setup_task = tg.create_task(
                hass.config_entries.async_setup(mock_entry.entry_id)
            )

            await event.wait()
            assert mock_entry.state is ConfigEntryState.SETUP_IN_PROGRESS
            inject_bluetooth_service_info(hass, MISSING_MANUFACTURER_DATA_SERVICE_INFO)
            inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

            assert await setup_task is True


async def test_setup_retry(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: Mock
) -> None:
    """Test setup creates expected devices."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

    original_read_char = mock_client.read_char.side_effect
    mock_client.read_char.side_effect = DeviceUnavailable
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY

    mock_client.read_char.side_effect = original_read_char

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_entry.state is ConfigEntryState.LOADED
