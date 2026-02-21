"""Test initialization for dk_fuelprices."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

from homeassistant.components.dk_fuelprices import (
    _setup,
    _update_listener,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
    remove_stale_devices,
)
from homeassistant.components.dk_fuelprices.const import (
    CONF_COMPANY,
    CONF_PRODUCTS,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_PRODUCTS, TEST_STATION

from tests.common import MockConfigEntry


async def test_update_listener_schedules_reload(hass: HomeAssistant) -> None:
    """Test update listener schedules an entry reload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: TEST_API_KEY})
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload_mock:
        await _update_listener(hass, config_entry)

    reload_mock.assert_called_once_with(config_entry.entry_id)


async def test_setup_creates_initial_subentry_and_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test setup converts legacy config data into subentry and creates coordinator."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        state=ConfigEntryState.SETUP_IN_PROGRESS,
        data={
            CONF_API_KEY: TEST_API_KEY,
            CONF_COMPANY: TEST_COMPANY,
            CONF_STATION: TEST_STATION,
            CONF_PRODUCTS: TEST_PRODUCTS,
        },
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.dk_fuelprices.APIClient") as mock_api_client:
        coordinator = mock_api_client.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()

        runtime_data = await _setup(hass, config_entry)
        assert runtime_data is not None
        assert len(runtime_data) == 1

    updated_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data == {CONF_API_KEY: TEST_API_KEY}
    assert len(updated_entry.subentries) == 1

    subentry_id = next(iter(updated_entry.subentries))
    mock_api_client.assert_called_once_with(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        TEST_PRODUCTS,
        subentry_id,
        updated_entry,
    )
    coordinator.async_config_entry_first_refresh.assert_awaited_once()


async def test_setup_returns_false_without_api_key(hass: HomeAssistant) -> None:
    """Test setup fails when API key is missing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={},
            )
        ],
    )
    config_entry.add_to_hass(hass)

    assert await _setup(hass, config_entry) is None


async def test_setup_legacy_entry_without_station_data(hass: HomeAssistant) -> None:
    """Test setup leaves legacy entry unchanged if station data is incomplete."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_API_KEY: TEST_API_KEY, CONF_COMPANY: TEST_COMPANY},
    )
    config_entry.add_to_hass(hass)

    runtime_data = await _setup(hass, config_entry)
    assert runtime_data == {}
    assert len(config_entry.subentries) == 0


async def test_migrate_entry_to_v2(hass: HomeAssistant) -> None:
    """Test migration from version 1 to version 2 with subentry creation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_COMPANY: TEST_COMPANY,
            CONF_STATION: TEST_STATION,
        },
        options={
            CONF_API_KEY: TEST_API_KEY,
            CONF_PRODUCTS: TEST_PRODUCTS,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 2
    assert entry.data == {CONF_API_KEY: TEST_API_KEY}
    assert entry.options == {}
    assert len(entry.subentries) == 1

    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == "station"
    assert subentry.unique_id == f"{TEST_COMPANY}_{TEST_STATION['id']}"
    assert subentry.data == {
        CONF_COMPANY: TEST_COMPANY,
        CONF_STATION: TEST_STATION,
        CONF_PRODUCTS: TEST_PRODUCTS,
    }


async def test_migrate_entry_noop_for_v2(hass: HomeAssistant) -> None:
    """Test migration is a no-op for already migrated entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_API_KEY: TEST_API_KEY},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True


async def test_async_remove_config_entry_device(hass: HomeAssistant) -> None:
    """Test config entry device removal decision with subentry identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={},
            )
        ],
    )
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    linked_device = SimpleNamespace(identifiers={(DOMAIN, subentry_id)})
    unlinked_device = SimpleNamespace(identifiers={(DOMAIN, "station_2")})

    assert (
        await async_remove_config_entry_device(
            hass, entry, cast(DeviceEntry, linked_device)
        )
        is False
    )
    assert (
        await async_remove_config_entry_device(
            hass, entry, cast(DeviceEntry, unlinked_device)
        )
        is True
    )


async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale devices are removed from the config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Valid",
                unique_id="valid_device",
                data={},
            )
        ],
    )
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "valid_device")},
        name="Valid device",
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "stale_device")},
        name="Stale device",
    )

    devices = {"valid": SimpleNamespace(deviceid="valid_device")}
    remove_stale_devices(hass, config_entry, devices)

    entries = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    identifiers = {next(iter(device.identifiers))[1] for device in entries}
    assert identifiers == {"valid_device"}


async def test_async_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setup/unload forwards and removes integration runtime data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                    CONF_PRODUCTS: TEST_PRODUCTS,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dk_fuelprices.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
    ):
        mock_api_client.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await async_setup_entry(hass, config_entry) is True
        assert len(config_entry.runtime_data) == 1

        assert await async_unload_entry(hass, config_entry) is True
        assert config_entry.runtime_data == {}
