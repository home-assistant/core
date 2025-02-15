"""Test init of LCN integration."""

from unittest.mock import Mock, patch

from pypck.connection import (
    PchkAuthenticationError,
    PchkConnectionFailedError,
    PchkConnectionRefusedError,
    PchkLcnNotConnectedError,
    PchkLicenseError,
)
from pypck.lcn_defs import LcnEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MockConfigEntry,
    MockPchkConnectionManager,
    create_config_entry,
    init_integration,
)


async def test_async_setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test a successful setup entry and unload of entry."""
    await init_integration(hass, entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_multiple_entries(
    hass: HomeAssistant, entry: MockConfigEntry, entry2
) -> None:
    """Test a successful setup and unload of multiple entries."""
    hass.http = Mock()
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager
    ):
        for config_entry in (entry, entry2):
            await init_integration(hass, config_entry)
            assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for config_entry in (entry, entry2):
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry if entry with same id already exists."""
    # setup first entry
    entry.source = config_entries.SOURCE_IMPORT
    entry.add_to_hass(hass)

    # create dummy entity for LCN platform as an orphan
    dummy_entity = entity_registry.async_get_or_create(
        "switch", DOMAIN, "dummy", config_entry=entry
    )

    # create dummy device for LCN platform as an orphan
    dummy_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id, 0, 7, False)},
        via_device=(DOMAIN, entry.entry_id),
    )

    assert dummy_entity in entity_registry.entities.values()
    assert dummy_device in device_registry.devices.values()


@pytest.mark.parametrize(
    "exception",
    [
        PchkAuthenticationError,
        PchkLicenseError,
        PchkConnectionRefusedError,
        PchkConnectionFailedError,
        PchkLcnNotConnectedError,
    ],
)
async def test_async_setup_entry_fails(
    hass: HomeAssistant, entry: MockConfigEntry, exception: Exception
) -> None:
    """Test that an error is handled properly."""
    with (
        patch(
            "homeassistant.components.lcn.PchkConnectionManager.async_connect",
            side_effect=exception,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "event",
    [LcnEvent.CONNECTION_LOST, LcnEvent.PING_TIMEOUT, LcnEvent.BUS_DISCONNECTED],
)
async def test_async_entry_reload_on_host_event_received(
    hass: HomeAssistant, entry: MockConfigEntry, event: LcnEvent
) -> None:
    """Test for config entry reload on certain host event received."""
    lcn_connection = await init_integration(hass, entry)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as async_schedule_reload:
        lcn_connection.fire_event(event)
        async_schedule_reload.assert_called_with(entry.entry_id)


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_migrate_1_1(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test migration config entry."""
    entry_v1_1 = create_config_entry("pchk_v1_1", version=(1, 1))
    await init_integration(hass, entry_v1_1)

    entry_migrated = hass.config_entries.async_get_entry(entry_v1_1.entry_id)

    assert entry_migrated.state is ConfigEntryState.LOADED
    assert entry_migrated.version == 3
    assert entry_migrated.minor_version == 1
    assert entry_migrated.data == snapshot


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_migrate_1_2(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test migration config entry."""
    entry_v1_2 = create_config_entry("pchk_v1_2", version=(1, 2))
    await init_integration(hass, entry_v1_2)

    entry_migrated = hass.config_entries.async_get_entry(entry_v1_2.entry_id)

    assert entry_migrated.state is ConfigEntryState.LOADED
    assert entry_migrated.version == 3
    assert entry_migrated.minor_version == 1
    assert entry_migrated.data == snapshot


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_migrate_2_1(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test migration config entry."""
    entry_v2_1 = create_config_entry("pchk_v2_1", version=(2, 1))
    await init_integration(hass, entry_v2_1)

    entry_migrated = hass.config_entries.async_get_entry(entry_v2_1.entry_id)
    assert entry_migrated.state is ConfigEntryState.LOADED
    assert entry_migrated.version == 3
    assert entry_migrated.minor_version == 1
    assert entry_migrated.data == snapshot


@pytest.mark.parametrize(
    ("entity_id", "replace"),
    [
        ("climate.climate1", ("-r1varsetpoint", "-var1.r1varsetpoint")),
        ("scene.romantic", ("-00", "-0.0")),
    ],
)
@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_entity_migration_on_2_1(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id, replace
) -> None:
    """Test entity.unique_id migration on config_entry migration from 2.1."""
    entry_v2_1 = create_config_entry("pchk_v2_1", version=(2, 1))
    await init_integration(hass, entry_v2_1)

    migrated_unique_id = entity_registry.async_get(entity_id).unique_id
    old_unique_id = migrated_unique_id.replace(*replace)
    entity_registry.async_update_entity(entity_id, new_unique_id=old_unique_id)
    assert entity_registry.async_get(entity_id).unique_id == old_unique_id

    await hass.config_entries.async_unload(entry_v2_1.entry_id)

    entry_v2_1 = create_config_entry("pchk_v2_1", version=(2, 1))
    await init_integration(hass, entry_v2_1)
    assert entity_registry.async_get(entity_id).unique_id == migrated_unique_id
