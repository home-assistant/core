"""Tests for the Hunter Douglas PowerView integration setup and device removal."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiopvapi.helpers.aiorequest import PvApiMaintenance
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.hunterdouglas_powerview.util import async_connect_hub
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_SERIAL


def _get_hub_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dr.DeviceEntry:
    """Return the hub device (the only one with no parent) for an entry."""
    return next(
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id is None
    )


async def test_setup_not_primary_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when the hub is not the primary hub."""
    mock_config_entry.add_to_hass(hass)
    hub = MagicMock(hub_address="1.2.3.4", role="Secondary")
    hub.name = "PowerView Hub"

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        AsyncMock(return_value=MagicMock(hub=hub)),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        "PowerView Hub (1.2.3.4) is performing role of Secondary Hub. Only the"
        " Primary Hub can manage shades"
    )


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_when_hub_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the hub cannot be reached."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hunterdouglas_powerview.util.Hub.query_firmware",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_when_room_data_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when fetching rooms fails after connecting."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hunterdouglas_powerview.Rooms.get_rooms",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_setup_retry_without_device_info(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the hub returns no device info."""
    mock_config_entry.add_to_hass(hass)

    async def _connect_without_device_info(hass_, address, api_version=None):
        api = await async_connect_hub(hass_, address, api_version)
        api.device_info = None
        return api

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        side_effect=_connect_without_device_info,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ghost devices are removed during setup, without any coordinator poll."""
    mock_config_entry.add_to_hass(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, MOCK_SERIAL)}
    )
    phantom = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(phantom.id) is None
    assert device_registry.async_get(hub.id) is not None


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
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    get_shades_kwargs: dict,
) -> None:
    """Test shade entities become unavailable when the hub update fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hunterdouglas_powerview.Shades.get_shades",
        **get_shades_kwargs,
    ):
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    covers = hass.states.async_all("cover")
    assert covers
    assert all(state.state == STATE_UNAVAILABLE for state in covers)


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_stale_shade_devices_removed_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a shade missing from the hub is removed; real shades and hub stay."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    existing = {device.id for device in entries}
    hub = next(device for device in entries if device.via_device_id is None)
    phantom = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(phantom.id) is None
    assert {
        d.id
        for d in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
    } == existing
