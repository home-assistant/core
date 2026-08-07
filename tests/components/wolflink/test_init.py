"""Test the Wolf SmartSet Service."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import attr
from freezegun.api import FrozenDateTimeFactory
from httpx import RequestError
import pytest
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, ParameterReadError

from homeassistant.components.wolflink.const import DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

LEGACY_CONFIG = {
    "device_name": "test-device",
    "device_id": 1234,
    "device_gateway": 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def _assert_v2_hub(entry: MockConfigEntry) -> None:
    """Assert an entry has been migrated to the v2 hub schema."""
    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.unique_id == "test-username"
    assert entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.mark.parametrize(
    ("stored_unique_id", "minor_version"),
    [
        pytest.param(1234, 1, id="v1.1_int_unique_id"),
        pytest.param("1234", 2, id="v1.2_str_unique_id"),
    ],
)
async def test_migration_v1_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    stored_unique_id: int | str,
    minor_version: int,
) -> None:
    """Test full v1 → v2.2 migration: entry, device, and entity reattachment.

    Covers v1.1 (int unique_id) and v1.2 (str unique_id) starting points,
    pre-existing devices/entities (including disabled-by-config-entry rows
    that must be re-flagged USER/DEVICE), and unique_id rewriting.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=stored_unique_id,
        data=LEGACY_CONFIG,
        version=1,
        minor_version=minor_version,
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, stored_unique_id)},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
        name="test-device",
    )
    # A stale disabled_by flag can't be set through the registry API, which
    # validates it against the config entry's disabled state; write it
    # directly to simulate existing storage.
    device = attr.evolve(device, disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY)
    device_registry.devices[device.id] = device
    entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="1234:6005200000",
        config_entry=config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_hub(config_entry)

    # Device identifier was rewritten to a string and remains attached to
    # the (now-migrated) hub entry; CONFIG_ENTRY disabled_by was rewritten
    # to USER (device) / DEVICE (entity) so disabled state survives.
    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, "1234")}
    assert migrated_device.config_entries == {config_entry.entry_id}
    assert migrated_device.disabled_by is dr.DeviceEntryDisabler.USER

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == config_entry.entry_id
    assert migrated_entity.config_subentry_id is None
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.DEVICE


async def test_migration_v1_2_to_v2_without_device(hass: HomeAssistant) -> None:
    """Test migration when the device-registry row is missing.

    This happens when the integration never finished its first setup —
    the migration must still bump the entry to v2.2 cleanly.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_hub(config_entry)


async def test_migration_skips_entity_from_other_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration ignores entities on the device that belong to another entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    other_entry = MockConfigEntry(domain="other", unique_id="other")
    config_entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        manufacturer=MANUFACTURER,
        name="test-device",
    )
    # This entity belongs to a different integration sharing the same device.
    other_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform="other",
        unique_id="other:sensor",
        config_entry=other_entry,
        device_id=device.id,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    # The other entry's entity must be untouched.
    assert (
        entity_registry.async_get(other_entity.entity_id).config_entry_id
        == other_entry.entry_id
    )


async def test_migration_merges_duplicate_v1_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test two v1 entries for the same account merge into one v2 hub entry."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": 1234},
        version=1,
        minor_version=2,
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="5678",
        data={**LEGACY_CONFIG, "device_id": 5678},
        version=1,
        minor_version=2,
    )
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    # Pre-register devices for both entries so the sibling-merge path also
    # exercises the device-reattachment branch.
    device_registry.async_get_or_create(
        config_entry_id=first_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        manufacturer=MANUFACTURER,
        name="test-device",
    )
    device_5678 = device_registry.async_get_or_create(
        config_entry_id=second_entry.entry_id,
        identifiers={(DOMAIN, "5678")},
        manufacturer=MANUFACTURER,
        name="second-device",
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        # Setting up the first entry loads the integration, which sets up and migrates
        # every wolflink entry: the first becomes the hub and the second merges into it.
        await hass.config_entries.async_setup(first_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    surviving = entries[0]
    assert surviving.entry_id == first_entry.entry_id
    assert surviving.version == 2
    assert surviving.minor_version == 2
    assert surviving.unique_id == "test-username"

    # The pre-existing device for 5678 was reattached to the surviving entry.
    device = device_registry.async_get(device_5678.id)
    assert device is not None
    assert device.config_entries == {surviving.entry_id}


async def test_migration_merge_into_disabled_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an enabled device merged onto a disabled hub entry gets disabled."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        version=2,
        minor_version=2,
        disabled_by=ConfigEntryDisabler.USER,
    )
    hub_entry.add_to_hass(hass)
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="5678",
        data={**LEGACY_CONFIG, "device_id": 5678},
        version=1,
        minor_version=2,
    )
    legacy_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=legacy_entry.entry_id,
        identifiers={(DOMAIN, "5678")},
        manufacturer=MANUFACTURER,
        name="test-device",
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(legacy_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].entry_id == hub_entry.entry_id

    # The device was reattached to the disabled hub entry, and its disabled
    # state now reflects the new owning entry's disabled state.
    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.config_entries == {hub_entry.entry_id}
    assert migrated_device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY


async def test_migration_v1_list_device_id(hass: HomeAssistant) -> None:
    """Test v1 migration tolerates device_id stored as a list from partial migrations."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": [1234]},
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_hub(config_entry)


async def test_migration_v1_empty_list_device_id(hass: HomeAssistant) -> None:
    """Test v1 migration returns early if device_id is an empty list."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": []},
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    # Migration returned early — entry is unchanged (still v1).
    assert config_entry.version == 1
    assert config_entry.minor_version == 2


async def test_setup_no_devices_on_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup loads cleanly even if the account has no devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.return_value = []
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor")


async def test_setup_multiple_devices(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that each device on the account gets its own coordinator and device entry.

    Verifies the multi-device path in async_setup_entry: two devices must produce
    two device-registry entries and two independent sets of entities with correctly
    namespaced unique_ids.
    """
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "first-device"),
        Device(9999, 5678, "second-device"),
    ]

    await setup_integration(hass, mock_config_entry)

    # Both devices must appear in the device registry.
    first = device_registry.async_get_device({(DOMAIN, "1234")})
    second = device_registry.async_get_device({(DOMAIN, "9999")})
    assert first is not None
    assert second is not None
    assert first.name == "first-device"
    assert second.name == "second-device"

    # Entities for each device carry the correct device-scoped unique_ids.
    entity_ids = hass.states.async_entity_ids("sensor")
    assert any("first_device" in eid for eid in entity_ids)
    assert any("second_device" in eid for eid in entity_ids)


async def test_migrate_future_version_aborts(hass: HomeAssistant) -> None:
    """Test migration refuses to downgrade a future-version entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        version=3,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_setup_fetch_parameters_fails(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device whose parameter fetch fails is skipped, not the whole entry."""
    mock_wolflink.fetch_parameters.side_effect = RequestError(
        "Unable to fetch parameters"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor")


async def test_system_share_id_forwarded_to_state_list(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test system_share_id is forwarded to fetch_system_state_list for shared systems."""
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "test-device", system_share_id=9999),
    ]

    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_system_state_list.assert_called_with(1234, 5678, 9999)


async def test_update_skipped_when_device_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an offline device makes its entities unavailable.

    On the next successful poll, parameters must be re-fetched because the
    cached value IDs may have rotated while the device was unreachable.
    """
    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_parameters.reset_mock()
    mock_wolflink.fetch_system_state_list.return_value = False

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_device_energy_parameter").state
        == STATE_UNAVAILABLE
    )

    mock_wolflink.fetch_system_state_list.return_value = True
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1
    assert hass.states.get("sensor.test_device_energy_parameter").state == "183"


@pytest.mark.parametrize(
    "side_effect",
    [
        RequestError("boom"),
        FetchFailed("boom"),
        InvalidAuth,
    ],
)
async def test_update_failure_modes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test recoverable update errors mark entities as unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_value.side_effect = side_effect
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_device_energy_parameter").state
        == STATE_UNAVAILABLE
    )


async def test_parameter_read_error_triggers_refetch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ParameterReadError flags parameters for re-fetch on the next cycle."""
    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_parameters.reset_mock()
    mock_wolflink.fetch_value.side_effect = ParameterReadError("stale")

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_device_energy_parameter").state
        == STATE_UNAVAILABLE
    )

    mock_wolflink.fetch_value.side_effect = None
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1
    assert hass.states.get("sensor.test_device_energy_parameter").state == "183"


async def test_refetch_flag_reset_on_fetch_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _refetch_parameters is reset even when the re-fetch itself fails.

    Regression test: if fetch_parameters raises during a re-fetch triggered by
    ParameterReadError, the flag must be cleared so subsequent cycles do not
    endlessly retry the parameter fetch on every update.
    """
    await setup_integration(hass, mock_config_entry)

    # Trigger the flag via ParameterReadError.
    mock_wolflink.fetch_value.side_effect = ParameterReadError("stale")
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Re-fetch itself fails — flag must still be cleared.
    mock_wolflink.fetch_parameters.reset_mock()
    mock_wolflink.fetch_parameters.side_effect = RequestError("cannot reach API")
    mock_wolflink.fetch_value.side_effect = None
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1

    # Next cycle must NOT retry the re-fetch — flag was cleared.
    mock_wolflink.fetch_parameters.side_effect = None
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1
