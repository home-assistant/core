"""Tests for the Hunter Douglas PowerView integration setup and device removal."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.hunterdouglas_powerview.util import async_connect_hub
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_MAC, MOCK_SERIAL


def _get_hub_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dr.DeviceEntry:
    """Return the hub device (the only one with no parent) for an entry."""
    return next(
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id is None
    )


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_not_primary_hub(hass: HomeAssistant) -> None:
    """Test setup fails when the hub is not the primary hub."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    hub = MagicMock(hub_address="1.2.3.4", role="Secondary")
    hub.name = "PowerView Hub"

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        AsyncMock(return_value=MagicMock(hub=hub)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == (
        "PowerView Hub (1.2.3.4) is performing role of Secondary Hub. Only the"
        " Primary Hub can manage shades"
    )


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_when_hub_unreachable(hass: HomeAssistant) -> None:
    """Test setup retries when the hub cannot be reached."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hunterdouglas_powerview.util.Hub.query_firmware",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_when_room_data_fails(hass: HomeAssistant) -> None:
    """Test setup retries when fetching rooms fails after connecting."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hunterdouglas_powerview.Rooms.get_rooms",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_without_device_info(hass: HomeAssistant) -> None:
    """Test setup retries when the hub returns no device info."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)

    async def _connect_without_device_info(hass_, address, api_version=None):
        api = await async_connect_hub(hass_, address, api_version)
        api.device_info = None
        return api

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        side_effect=_connect_without_device_info,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_sets_missing_unique_id(hass: HomeAssistant) -> None:
    """Test setup fills in a missing unique id on an up-to-date entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.2.3.4"}, version=1, minor_version=2
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_migrate_entry_without_unique_id(hass: HomeAssistant) -> None:
    """Test migrating a version 1.1 entry that has no unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.2.3.4"}, version=1, minor_version=1
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == MOCK_SERIAL
    assert entry.minor_version == 2


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_stale_shade_devices_removed_on_setup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test ghost devices are removed during setup, without any coordinator poll."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, MOCK_SERIAL)}
    )
    phantom = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(phantom.id) is None
    assert device_registry.async_get(hub.id) is not None
