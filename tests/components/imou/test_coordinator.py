"""Tests for Imou data update coordinator."""

from unittest.mock import AsyncMock, MagicMock

from pyimouapi.ha_device import ImouHaDevice
import pytest

from homeassistant.components.imou.coordinator import ImouDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .util import CONFIG_ENTRY_DATA

from tests.common import MockConfigEntry


def test_device_manager_property(hass: HomeAssistant) -> None:
    """Coordinator exposes the Imou device manager."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="coord-1",
    )
    manager = MagicMock()
    coord = ImouDataUpdateCoordinator(hass, manager, entry)
    assert coord.device_manager is manager


async def test_update_data_fetches_devices_when_empty(hass: HomeAssistant) -> None:
    """First update loads devices from the API when the cache is empty."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="coord-2",
    )
    device = ImouHaDevice("d1", "n", "m", "md", "1")
    manager = MagicMock()
    manager.async_get_devices = AsyncMock(return_value=[device])
    manager.async_update_device_status = AsyncMock()

    coord = ImouDataUpdateCoordinator(hass, manager, entry)
    await coord._async_update_data()

    assert coord.devices == [device]
    manager.async_get_devices.assert_awaited_once()
    manager.async_update_device_status.assert_awaited_once_with(device)

    await coord._async_update_data()
    manager.async_get_devices.assert_awaited_once()
    assert manager.async_update_device_status.await_count == 2


async def test_update_data_raises_update_failed_on_error(hass: HomeAssistant) -> None:
    """Device manager errors are wrapped in UpdateFailed."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="coord-3",
    )
    device = ImouHaDevice("d1", "n", "m", "md", "1")
    manager = MagicMock()
    manager.async_get_devices = AsyncMock(return_value=[device])
    manager.async_update_device_status = AsyncMock(side_effect=RuntimeError("boom"))

    coord = ImouDataUpdateCoordinator(hass, manager, entry)

    with pytest.raises(UpdateFailed, match="Error updating Imou devices"):
        await coord._async_update_data()


async def test_update_data_maps_timeout_error_from_fetch(
    hass: HomeAssistant,
) -> None:
    """TimeoutError while loading devices is mapped to UpdateFailed."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="coord-4",
    )
    manager = MagicMock()
    manager.async_get_devices = AsyncMock(side_effect=TimeoutError("slow"))
    coord = ImouDataUpdateCoordinator(hass, manager, entry)

    with pytest.raises(UpdateFailed, match="Timeout while fetching data"):
        await coord._async_update_data()
