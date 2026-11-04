"""Tests for iCloud account storage sensors and polling."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.exceptions import PyiCloudAPIResponseException
from pyicloud.services.account import AccountStorage
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import MagicMock
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DEVICE


@pytest.mark.parametrize(
    ("key", "expected", "unit", "device_class"),
    [
        ("total", 100.0, "GB", "data_size"),
        ("used", 40.0, "GB", "data_size"),
        ("free", 60.0, "GB", "data_size"),
        ("percentage", 40.0, "%", None),
        ("media_photos", 30.0, "GB", "data_size"),
        ("media_backup", 10.0, "GB", "data_size"),
    ],
)
async def test_storage_sensor(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    devices_config_entry: MockConfigEntry,
    key: str,
    expected: float,
    unit: str,
    device_class: str | None,
) -> None:
    """Storage is available without Find My devices and belongs to the account."""
    await setup_entry(Platform.SENSOR)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"test_account_id_storage_{key}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == expected
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes.get("device_class") == device_class
    assert state.attributes["state_class"] == "measurement"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_account_id_account"), devices_config_entry.entry_id
    )
    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert entity_registry.async_get(entity_id).device_id == device.id
    icloud_service.account.refresh_storage.assert_called_once_with()


async def test_storage_refresh_and_discovery(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """New categories appear after refresh and missing categories become unknown."""
    await setup_entry(Platform.SENSOR)
    coordinator = devices_config_entry.runtime_data.storage_coordinator
    assert coordinator.update_interval == timedelta(hours=1)
    icloud_service.account.refresh_storage.return_value = AccountStorage(
        {
            "storageUsageInfo": {
                "totalStorageInBytes": 200_000_000_000,
                "usedStorageInBytes": 20_000_000_000,
            },
            "storageUsageByMedia": [
                {"mediaKey": "docs", "displayLabel": "Documents", "usageInBytes": 0},
                {
                    "mediaKey": "other",
                    "displayLabel": "Other",
                    "usageInBytes": 20_000_000_000,
                },
            ],
        }
    )
    await _async_poll_storage(hass, freezer)

    for key, expected in (
        ("total", "200.0"),
        ("used", "20.0"),
        ("free", "180.0"),
        ("percentage", "10.0"),
        ("media_photos", STATE_UNKNOWN),
        ("media_docs", "0.0"),
        ("media_other", "20.0"),
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"test_account_id_storage_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == expected
    assert icloud_service.account.refresh_storage.call_count == 2
    count = len(
        er.async_entries_for_config_entry(
            entity_registry, devices_config_entry.entry_id
        )
    )
    await _async_poll_storage(hass, freezer)
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, devices_config_entry.entry_id
            )
        )
        == count
    )


@pytest.mark.parametrize(
    "error",
    [
        PyiCloudAPIResponseException("Storage unavailable"),
        RequestsConnectionError("Connection failed"),
        ValueError("Invalid JSON"),
        TimeoutError(),
    ],
)
async def test_storage_failure_and_recovery(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    error: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A storage outage leaves device sensors working and recovers on refresh."""
    icloud_service.devices.add(DEVICE)
    await setup_entry(Platform.SENSOR)
    used_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test_account_id_storage_used"
    )
    battery_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "device1_battery"
    )
    battery = hass.states.get(battery_id).state
    icloud_service.account.refresh_storage.side_effect = error

    await _async_poll_storage(hass, freezer)
    assert hass.states.get(used_id).state == STATE_UNAVAILABLE
    assert hass.states.get(battery_id).state == battery

    icloud_service.account.refresh_storage.side_effect = None
    await _async_poll_storage(hass, freezer)
    assert hass.states.get(used_id).state == "40.0"


@pytest.mark.parametrize(
    ("usage", "expected_used", "expected_free", "expected_percentage"),
    [
        ({}, STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN),
        (
            {"usedStorageInBytes": 0, "totalStorageInBytes": 100_000_000_000},
            "0.0",
            "100.0",
            "0.0",
        ),
        (
            {"usedStorageInBytes": 0, "totalStorageInBytes": 0},
            "0.0",
            "0.0",
            STATE_UNKNOWN,
        ),
        (
            {"totalStorageInBytes": 100_000_000_000},
            STATE_UNKNOWN,
            STATE_UNKNOWN,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_storage_missing_or_zero_usage(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    usage: dict[str, int],
    expected_used: str,
    expected_free: str,
    expected_percentage: str,
) -> None:
    """Missing data stays unknown and empty storage is a valid measurement."""
    icloud_service.account.refresh_storage.return_value = AccountStorage(
        {"storageUsageInfo": usage}
    )
    await setup_entry(Platform.SENSOR)
    for key, expected in (
        ("used", expected_used),
        ("free", expected_free),
        ("percentage", expected_percentage),
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"test_account_id_storage_{key}"
        )
        assert hass.states.get(entity_id).state == expected


async def test_storage_initial_failure(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Initial failure loads unavailable sensors and later discovers categories."""
    icloud_service.account.refresh_storage.side_effect = PyiCloudAPIResponseException(
        "Unavailable"
    )
    await setup_entry(Platform.SENSOR)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test_account_id_storage_used"
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    icloud_service.account.refresh_storage.side_effect = None
    await _async_poll_storage(hass, freezer)
    assert hass.states.get(entity_id).state == "40.0"
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test_account_id_storage_media_photos"
    )


async def test_storage_without_authenticated_account(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unavailable authentication does not send a storage request."""
    await setup_entry(Platform.SENSOR)
    account = devices_config_entry.runtime_data
    account.api = None
    await hass.async_add_executor_job(account.cancel_fetch)
    icloud_service.account.refresh_storage.reset_mock()
    await _async_poll_storage(hass, freezer)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test_account_id_storage_used"
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    icloud_service.account.refresh_storage.assert_not_called()


async def test_storage_hourly_poll_and_unload(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Storage refreshes hourly and stops polling after the entry is unloaded."""
    await setup_entry(Platform.SENSOR)
    icloud_service.account.refresh_storage.reset_mock()

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    icloud_service.account.refresh_storage.assert_called_once_with()

    with patch("homeassistant.components.icloud.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_unload(devices_config_entry.entry_id)
    icloud_service.account.refresh_storage.reset_mock()
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    icloud_service.account.refresh_storage.assert_not_called()


async def _async_poll_storage(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance to the next scheduled storage poll."""
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
