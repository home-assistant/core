"""Tests for Tomorrow.io init."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pytomorrowio.exceptions import CantConnectException

from homeassistant.components.tomorrowio.const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    SUBENTRY_TYPE_LOCATION,
)
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    TEST_LOCATION,
    TEST_SUBENTRY_ID,
    make_location_subentry_data,
    make_v2_config_entry,
)
from .const import API_KEY

from tests.common import MockConfigEntry, async_fire_time_changed

HOME_LOCATION = {CONF_LATITUDE: 80.0, CONF_LONGITUDE: 80.0}
WORK_LOCATION = {CONF_LATITUDE: 81.0, CONF_LONGITUDE: 81.0}


def make_v1_config_entry(
    api_key: str,
    location: dict[str, float],
    name: str,
    timestep: int,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Return a version 1 Tomorrow.io config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={CONF_API_KEY: api_key, CONF_LOCATION: location, CONF_NAME: name},
        options={CONF_TIMESTEP: timestep},
        unique_id=(f"{api_key}_{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}"),
        version=1,
        disabled_by=disabled_by,
    )


async def test_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading entry."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0


async def test_setup_entry_not_ready(
    hass: HomeAssistant, tomorrowio_config_entry_update: AsyncMock
) -> None:
    """Test entry setup retries when the first refresh fails."""
    tomorrowio_config_entry_update.side_effect = CantConnectException
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_intervals(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tomorrowio_config_entry_update: AsyncMock,
) -> None:
    """Test coordinator update interval scales with the number of locations."""
    config_entry = make_v2_config_entry(
        subentries_data=[
            make_location_subentry_data(
                location=HOME_LOCATION,
                name="Home",
                timestep=1,
                subentry_id="subentry_home",
            ),
            make_location_subentry_data(
                location=WORK_LOCATION,
                name="Work",
                timestep=1,
                subentry_id="subentry_work",
            ),
        ]
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # One API call per location on the initial refresh
    assert len(tomorrowio_config_entry_update.call_args_list) == 2

    tomorrowio_config_entry_update.reset_mock()

    # Two locations with two API requests per call and a max of 100 requests per
    # day results in an update interval of ceil(24 * 60 * 2 * 2 / 90) = 64 minutes
    freezer.tick(timedelta(minutes=63))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(tomorrowio_config_entry_update.call_args_list) == 0

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(tomorrowio_config_entry_update.call_args_list) == 2


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Realistic default title from the old flow; the migration strips the
    # redundant integration-name prefix for the subentry.
    config_entry = make_v1_config_entry(API_KEY, HOME_LOCATION, "Tomorrow.io - Home", 1)
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, API_KEY)},
        manufacturer="Tomorrow.io",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_entry = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "aa_80.0_80.0_daily",
        config_entry=config_entry,
        device_id=device.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.title == "Tomorrow.io"
    assert config_entry.unique_id == API_KEY
    assert config_entry.data == {CONF_API_KEY: API_KEY}
    assert config_entry.options == {}
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(config_entry.subentries) == 1
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_LOCATION
    assert subentry.title == "Home"
    assert subentry.unique_id == "80.0_80.0"
    assert subentry.data == {
        CONF_LOCATION: HOME_LOCATION,
        CONF_NAME: "Home",
        CONF_TIMESTEP: 1,
    }

    # Verify the device was re-identified and linked to the subentry
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, subentry.subentry_id)}
    )
    assert device is not None
    assert device.config_entries_subentries == {
        config_entry.entry_id: {subentry.subentry_id}
    }

    # Verify the entity kept its unique ID and was linked to the subentry
    migrated_entity_entry = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entity_entry is not None
    assert migrated_entity_entry.unique_id == "aa_80.0_80.0_daily"
    assert migrated_entity_entry.config_entry_id == config_entry.entry_id
    assert migrated_entity_entry.config_subentry_id == subentry.subentry_id


async def test_migrate_entry_v1_to_v2_merge_same_api_key(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration merges v1 entries with the same API key."""
    entry1 = make_v1_config_entry(API_KEY, HOME_LOCATION, "Home", 1)
    entry2 = make_v1_config_entry(API_KEY, WORK_LOCATION, "Work", 5)
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    device1 = device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, API_KEY)},
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, API_KEY)},
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_entry_1 = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "aa_80.0_80.0_daily",
        config_entry=entry1,
        device_id=device1.id,
    )
    entity_entry_2 = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "aa_81.0_81.0_daily",
        config_entry=entry2,
        device_id=device2.id,
    )

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    assert entry1.version == 2
    assert entry1.title == "Tomorrow.io"
    assert entry1.unique_id == API_KEY
    assert entry1.data == {CONF_API_KEY: API_KEY}
    assert entry1.state is ConfigEntryState.LOADED

    # Verify entry2 was removed
    assert hass.config_entries.async_get_entry(entry2.entry_id) is None

    # Verify entry1 has two subentries with the per-entry timestep preserved
    assert len(entry1.subentries) == 2
    subentries = {
        subentry.unique_id: subentry for subentry in entry1.subentries.values()
    }
    home_subentry = subentries["80.0_80.0"]
    assert home_subentry.title == "Home"
    assert home_subentry.data == {
        CONF_LOCATION: HOME_LOCATION,
        CONF_NAME: "Home",
        CONF_TIMESTEP: 1,
    }
    work_subentry = subentries["81.0_81.0"]
    assert work_subentry.title == "Work"
    assert work_subentry.data == {
        CONF_LOCATION: WORK_LOCATION,
        CONF_NAME: "Work",
        CONF_TIMESTEP: 5,
    }

    # Verify both devices were moved to entry1 and linked to their subentries
    for subentry, device_id in (
        (home_subentry, device1.id),
        (work_subentry, device2.id),
    ):
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        assert device is not None
        assert device.id == device_id
        assert device.config_entries_subentries == {
            entry1.entry_id: {subentry.subentry_id}
        }

    # Verify entities from both entries were moved to entry1
    for entity_entry, subentry in (
        (entity_entry_1, home_subentry),
        (entity_entry_2, work_subentry),
    ):
        migrated_entity_entry = entity_registry.async_get(entity_entry.entity_id)
        assert migrated_entity_entry is not None
        assert migrated_entity_entry.config_entry_id == entry1.entry_id
        assert migrated_entity_entry.config_subentry_id == subentry.subentry_id


async def test_migrate_entry_v1_to_v2_different_api_keys(
    hass: HomeAssistant,
) -> None:
    """Test migration keeps separate entries for different API keys."""
    entry1 = make_v1_config_entry(API_KEY, HOME_LOCATION, "Home", 1)
    entry2 = make_v1_config_entry("bb", WORK_LOCATION, "Work", 5)
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    for entry, api_key, subentry_unique_id in (
        (entry1, API_KEY, "80.0_80.0"),
        (entry2, "bb", "81.0_81.0"),
    ):
        assert entry.version == 2
        assert entry.title == "Tomorrow.io"
        assert entry.unique_id == api_key
        assert entry.data == {CONF_API_KEY: api_key}
        assert entry.state is ConfigEntryState.LOADED
        assert len(entry.subentries) == 1
        subentry = next(iter(entry.subentries.values()))
        assert subentry.unique_id == subentry_unique_id


async def test_migrate_entry_v1_to_v2_disabled_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration updates disabled_by when merging disabled and enabled entries."""
    entry1 = make_v1_config_entry(API_KEY, HOME_LOCATION, "Home", 1)
    entry2 = make_v1_config_entry(
        API_KEY, WORK_LOCATION, "Work", 5, disabled_by=ConfigEntryDisabler.USER
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, API_KEY)},
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, API_KEY)},
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    entity_entry_2 = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "aa_81.0_81.0_daily",
        config_entry=entry2,
        device_id=device2.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    assert entry1.version == 2
    assert entry1.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_get_entry(entry2.entry_id) is None
    assert len(entry1.subentries) == 2
    work_subentry = next(
        subentry
        for subentry in entry1.subentries.values()
        if subentry.unique_id == "81.0_81.0"
    )

    # The device and entity of the disabled entry are no longer disabled by a
    # config entry, so the disabled_by flag must have been updated
    migrated_device = device_registry.async_get(device2.id)
    assert migrated_device is not None
    assert migrated_device.disabled_by is dr.DeviceEntryDisabler.USER
    assert migrated_device.config_entries_subentries == {
        entry1.entry_id: {work_subentry.subentry_id}
    }

    migrated_entity_entry = entity_registry.async_get(entity_entry_2.entity_id)
    assert migrated_entity_entry is not None
    assert migrated_entity_entry.disabled_by is er.RegistryEntryDisabler.DEVICE
    assert migrated_entity_entry.config_subentry_id == work_subentry.subentry_id


async def test_migration_resumes_after_interruption(hass: HomeAssistant) -> None:
    """Test an interrupted migration completes on the next start.

    A previously migrated v2 entry must not crash the migration and must
    adopt remaining v1 entries sharing its API key as subentries.
    """
    migrated = make_v2_config_entry()
    migrated.add_to_hass(hass)
    leftover = make_v1_config_entry(API_KEY, WORK_LOCATION, "Work", 5)
    leftover.add_to_hass(hass)

    await hass.config_entries.async_setup(migrated.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(leftover.entry_id) is None
    assert migrated.version == 2
    assert migrated.state is ConfigEntryState.LOADED
    subentries = migrated.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)
    assert len(subentries) == 2
    work_subentry = next(s for s in subentries if s.title == "Work")
    assert work_subentry.data[CONF_TIMESTEP] == 5


async def test_reconfigure_location_move_keeps_entity_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test moving a location's coordinates preserves entity identities."""
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    weather_entity_id = "weather.tomorrow_io_daily"
    entry_before = entity_registry.async_get(weather_entity_id)
    assert entry_before is not None
    assert f"_{TEST_LOCATION[CONF_LATITUDE]}_" in entry_before.unique_id

    result = await config_entry.start_subentry_reconfigure_flow(hass, TEST_SUBENTRY_ID)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_LOCATION: WORK_LOCATION,
            CONF_TIMESTEP: DEFAULT_TIMESTEP,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    entry_after = entity_registry.async_get(weather_entity_id)
    assert entry_after is not None
    assert entry_after.id == entry_before.id
    assert f"_{WORK_LOCATION[CONF_LATITUDE]}_" in entry_after.unique_id
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.unique_id == (
        f"{WORK_LOCATION[CONF_LATITUDE]}_{WORK_LOCATION[CONF_LONGITUDE]}"
    )


async def test_migration_resumes_after_subentry_persisted(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test resuming when a subentry persisted but its v1 entry remains.

    Interruption between async_add_subentry and the removal of the source
    entry must not abort with already_configured on the next start; the
    persisted subentry is reused and the leftover entry's entities move
    onto it.
    """
    work_subentry_id = "workworkworkworkworkworkwo"
    migrated = make_v2_config_entry(
        subentries_data=[
            make_location_subentry_data(),
            make_location_subentry_data(
                location=WORK_LOCATION, name="Work", subentry_id=work_subentry_id
            ),
        ]
    )
    migrated.add_to_hass(hass)
    leftover = make_v1_config_entry(API_KEY, WORK_LOCATION, "Work", 5)
    leftover.add_to_hass(hass)
    orphan = entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        f"{API_KEY}_{WORK_LOCATION[CONF_LATITUDE]}_{WORK_LOCATION[CONF_LONGITUDE]}_daily",
        config_entry=leftover,
    )

    await hass.config_entries.async_setup(migrated.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(leftover.entry_id) is None
    assert migrated.state is ConfigEntryState.LOADED
    assert len(migrated.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)) == 2
    moved = entity_registry.async_get(orphan.entity_id)
    assert moved is not None
    assert moved.config_entry_id == migrated.entry_id
    assert moved.config_subentry_id == work_subentry_id


async def test_migration_uses_customized_entry_title(hass: HomeAssistant) -> None:
    """Test a UI-renamed entry keeps its custom name for the location.

    Renames update the entry title but not the stored CONF_NAME, so the
    title must win.
    """
    config_entry = make_v1_config_entry(API_KEY, HOME_LOCATION, "Tomorrow.io - Home", 1)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, title="Casa")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.title == "Casa"
    assert subentry.data[CONF_NAME] == "Casa"


async def test_polling_disabled_pref(
    hass: HomeAssistant,
    tomorrowio_config_entry_update: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the system option to disable polling is honored (issue #177695).

    The coordinator previously had no config entry, so the preference was
    ignored. Scheduled refreshes must stop; manual refresh must still work.
    """
    config_entry = make_v2_config_entry()
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, pref_disable_polling=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    tomorrowio_config_entry_update.reset_mock()

    freezer.tick(timedelta(minutes=65))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(tomorrowio_config_entry_update.call_args_list) == 0

    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "weather.tomorrow_io_daily"},
        blocking=True,
    )
    assert len(tomorrowio_config_entry_update.call_args_list) == 1
