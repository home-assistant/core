"""Tests for stale shade cleanup in the PowerView coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiopvapi.helpers.aiorequest import PvApiMaintenance
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
@pytest.mark.parametrize(
    "get_shades_kwargs",
    [
        {"side_effect": PvApiMaintenance},
        {"side_effect": TimeoutError},
        {"return_value": None},
    ],
    ids=["maintenance", "hub_error", "no_data"],
)
async def test_refresh_failures(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    get_shades_kwargs: dict,
) -> None:
    """Test the coordinator marks the update failed on each error path."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    with patch.object(coordinator.shades, "get_shades", AsyncMock(**get_shades_kwargs)):
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not coordinator.last_update_success


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_stale_shade_devices_removed_on_refresh(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a shade missing from the hub is removed; real shades and hub stay."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    existing = {device.id for device in entries}
    hub = next(device for device in entries if device.via_device_id is None)
    phantom = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(phantom.id) is None
    assert {
        d.id for d in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    } == existing
