"""Test migration and rediscovery of legacy Gree config entries."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.gree.const import CONF_IDENTIFIER, DOMAIN
from homeassistant.components.gree.discovery import (
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import build_device_mock


def _add_legacy_entry(
    hass: HomeAssistant,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Add a shared v1 entry as if restored from storage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="gree",
        data={},
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    "identifiers", [(), ("legacy-device",)], ids=["empty", "populated"]
)
async def test_legacy_entry_becomes_persistent_discovery_owner(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identifiers: tuple[str, ...],
) -> None:
    """Migration retains the owner and all records without enrolling devices."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass)
    other = MockConfigEntry(domain="example", version=2, unique_id="other", data={})
    other.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("example", "other")},
    )
    other_entity = entity_registry.async_get_or_create(
        "sensor",
        "example",
        "other",
        config_entry=other,
        device_id=other_device.id,
    )
    old_devices = []
    old_entities = []
    for identifier in identifiers:
        old_device = device_registry.async_get_or_create(
            config_entry_id=source.entry_id,
            identifiers={(DOMAIN, identifier)},
        )
        old_devices.append(old_device)
        old_entities.append(
            entity_registry.async_get_or_create(
                "climate",
                DOMAIN,
                identifier,
                config_entry=source,
                device_id=old_device.id,
            )
        )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.config_entries.async_get_entry(source.entry_id) is source
    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == DOMAIN
    assert source.data == {}
    assert hass.config_entries.async_entries(DOMAIN) == [source]
    assert (
        dr.async_entries_for_config_entry(device_registry, source.entry_id)
        == old_devices
    )
    assert (
        er.async_entries_for_config_entry(entity_registry, source.entry_id)
        == old_entities
    )
    assert dr.async_entries_for_config_entry(device_registry, other.entry_id) == [
        other_device
    ]
    assert er.async_entries_for_config_entry(entity_registry, other.entry_id) == [
        other_entity
    ]
    assert not hass.states.async_all("climate")
    assert not hass.config_entries.flow.async_progress()
    device().bind.assert_not_awaited()
    device().update_state.assert_not_awaited()


async def test_disabled_legacy_entry_converts_when_enabled(
    hass: HomeAssistant,
    discovery: MagicMock,
) -> None:
    """A disabled source converts only when enabled and can stop discovery again."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass, ConfigEntryDisabler.USER)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert source.state is ConfigEntryState.NOT_LOADED
    assert source.version == 1
    assert source.disabled_by is ConfigEntryDisabler.USER
    assert not discovery.instances

    await hass.config_entries.async_set_disabled_by(source.entry_id, None)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert source.state is ConfigEntryState.LOADED
    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == DOMAIN
    assert source.data == {}
    assert hass.config_entries.async_get_entry(source.entry_id) is source

    await hass.config_entries.async_set_disabled_by(
        source.entry_id, ConfigEntryDisabler.USER
    )
    assert source.state is ConfigEntryState.NOT_LOADED
    assert source.disabled_by is ConfigEntryDisabler.USER
    assert hass.config_entries.async_entries(DOMAIN) == [source]


async def test_late_enrollment_preserves_legacy_records(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device returning after orphan expiry keeps its IDs and user settings."""
    candidate = device()
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(DOMAIN, candidate.device_info.mac)},
    )
    old_device = device_registry.async_update_device(
        old_device.id, name_by_user="Bedroom AC"
    )
    old_entity = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        candidate.device_info.mac,
        config_entry=source,
        device_id=old_device.id,
        suggested_object_id="custom_bedroom",
    )
    old_entity = entity_registry.async_update_entity(
        old_entity.entity_id,
        name="Bedroom temperature",
        icon="mdi:air-conditioner",
    )
    entity_registry.async_update_entity_options(
        old_entity.entity_id, "conversation", {"should_expose": False}
    )
    old_switch = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{candidate.device_info.mac}_light",
        config_entry=source,
        device_id=old_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
        hidden_by=er.RegistryEntryHider.USER,
    )
    offline_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(DOMAIN, "offline-device")},
    )
    offline_entity = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "offline-device",
        config_entry=source,
        device_id=offline_device.id,
    )
    unmatched_entity = entity_registry.async_get_or_create(
        "switch", DOMAIN, "unmatched", config_entry=source
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(days=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    dr.async_cleanup(hass, device_registry, entity_registry)
    entity_registry.async_purge_expired_orphaned_entities()

    assert device_registry.async_get(old_device.id) == old_device
    assert (
        entity_registry.async_get(old_entity.entity_id).config_entry_id
        == source.entry_id
    )
    assert entity_registry.async_get(old_switch.entity_id) == old_switch
    discovery.mock_devices = [candidate]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=device_info_to_data(candidate.device_info),
    )
    assert result["step_id"] == "discovery_confirm"
    assert hass.config_entries.async_entries(DOMAIN) == [source]
    candidate.bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == device_info_to_data(candidate.device_info)
    assert hass.config_entries.async_entries(DOMAIN) == [source, entry]
    transferred_device = device_registry.async_get(old_device.id)
    assert transferred_device.config_entry_id == entry.entry_id
    assert transferred_device.name_by_user == "Bedroom AC"
    transferred_entity = entity_registry.async_get(old_entity.entity_id)
    assert transferred_entity.config_entry_id == entry.entry_id
    assert transferred_entity.id == old_entity.id
    assert transferred_entity.device_id == old_device.id
    assert transferred_entity.name == "Bedroom temperature"
    assert transferred_entity.icon == "mdi:air-conditioner"
    assert transferred_entity.options["conversation"] == {"should_expose": False}
    assert hass.states.get(old_entity.entity_id) is not None
    transferred_switch = entity_registry.async_get(old_switch.entity_id)
    assert transferred_switch.config_entry_id == entry.entry_id
    assert transferred_switch.disabled_by is er.RegistryEntryDisabler.USER
    assert transferred_switch.hidden_by is er.RegistryEntryHider.USER
    assert dr.async_entries_for_config_entry(device_registry, source.entry_id) == [
        offline_device
    ]
    assert er.async_entries_for_config_entry(entity_registry, source.entry_id) == [
        offline_entity,
        unmatched_entity,
    ]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert device_registry.async_get(old_device.id).config_entry_id == entry.entry_id
    assert entity_registry.async_get(old_entity.entity_id).id == old_entity.id
    assert hass.states.get(old_entity.entity_id) is not None


@pytest.mark.parametrize(
    "entity_descriptions",
    [
        pytest.param((), id="device-only"),
        pytest.param(
            ((Platform.CLIMATE, ""), (Platform.SWITCH, "_light")), id="with-entities"
        ),
    ],
)
async def test_transfer_preserves_legacy_identifier_spelling(
    hass: HomeAssistant,
    device: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entity_descriptions: tuple[tuple[Platform, str], ...],
) -> None:
    """Match by device identity while preserving the legacy entity unique IDs."""
    source = _add_legacy_entry(hass)
    legacy_identifier = "AA:BB:CC:11:22:33"
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(DOMAIN, legacy_identifier)},
    )
    old_entities = [
        entity_registry.async_get_or_create(
            platform,
            DOMAIN,
            f"{legacy_identifier}{suffix}",
            config_entry=source,
            device_id=old_device.id,
        )
        for platform, suffix in entity_descriptions
    ]
    device.side_effect = lambda info: build_device_mock(identifier=info.mac)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_IDENTIFIER] == legacy_identifier
    assert device_registry.async_get(old_device.id).config_entry_id == entry.entry_id
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 1
    assert (
        entity_registry.async_get_entity_id(Platform.CLIMATE, DOMAIN, "aabbcc112233")
        is None
    )
    for old_entity in old_entities:
        migrated = entity_registry.async_get(old_entity.entity_id)
        assert migrated.id == old_entity.id
        assert migrated.unique_id == old_entity.unique_id
        assert migrated.config_entry_id == entry.entry_id


@pytest.mark.parametrize(
    ("source_disabled_by", "device_disabled_by"),
    [
        pytest.param(None, dr.DeviceEntryDisabler.USER, id="disabled-device"),
        pytest.param(ConfigEntryDisabler.USER, None, id="disabled-source"),
    ],
)
async def test_manual_enrollment_preserves_disabled_device(
    hass: HomeAssistant,
    device: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    source_disabled_by: ConfigEntryDisabler | None,
    device_disabled_by: dr.DeviceEntryDisabler | None,
) -> None:
    """Explicit enrollment does not implicitly enable a disabled legacy device."""
    source = _add_legacy_entry(hass, source_disabled_by)
    identifier = device().device_info.mac
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(DOMAIN, identifier)},
        disabled_by=device_disabled_by,
    )
    old_entity = entity_registry.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        identifier,
        config_entry=source,
        device_id=old_device.id,
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "pick_device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: normalize_identifier(identifier)}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = result["result"]
    migrated_device = device_registry.async_get(old_device.id)
    assert migrated_device.config_entry_id == entry.entry_id
    assert migrated_device.disabled_by is dr.DeviceEntryDisabler.USER
    migrated_entity = entity_registry.async_get(old_entity.entity_id)
    assert migrated_entity.id == old_entity.id
    assert migrated_entity.config_entry_id == entry.entry_id
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.DEVICE
    assert hass.states.get(old_entity.entity_id) is None
    assert source.disabled_by is source_disabled_by


@pytest.mark.parametrize(
    ("conflict_owner", "conflict_identifier"),
    [
        pytest.param("source", "AA:BB:CC:11:22:33", id="ambiguous-legacy-identity"),
        pytest.param("target", "aabbcc112233", id="destination-collision"),
    ],
)
async def test_conflicting_transfer_keeps_source_records(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    conflict_owner: str,
    conflict_identifier: str,
) -> None:
    """Failed transfers preserve source records and can retry after reconciliation."""
    discovery.mock_devices.clear()
    source = _add_legacy_entry(hass)
    info = device().device_info
    target = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=normalize_identifier(info.mac),
        data=device_info_to_data(info),
    )
    target.add_to_hass(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id, identifiers={(DOMAIN, info.mac)}
    )
    old_entity = entity_registry.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        info.mac,
        config_entry=source,
        device_id=old_device.id,
    )
    owners = {"source": source, "target": target}
    conflict = device_registry.async_get_or_create(
        config_entry_id=owners[conflict_owner].entry_id,
        identifiers={(DOMAIN, conflict_identifier)},
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert target.state is ConfigEntryState.SETUP_ERROR
    assert device_registry.async_get(old_device.id) == old_device
    retained_entity = entity_registry.async_get(old_entity.entity_id)
    assert retained_entity.id == old_entity.id
    assert retained_entity.config_entry_id == source.entry_id
    assert retained_entity.device_id == old_device.id
    assert device_registry.async_get(conflict.id) == conflict

    device_registry.async_remove_device(conflict.id)
    assert await hass.config_entries.async_reload(target.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert target.state is ConfigEntryState.LOADED
    assert device_registry.async_get(old_device.id).config_entry_id == target.entry_id
    assert (
        entity_registry.async_get(old_entity.entity_id).config_entry_id
        == target.entry_id
    )
    assert hass.states.get(old_entity.entity_id) is not None


async def test_transfer_preserves_system_preferences(
    hass: HomeAssistant,
    device: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retain system preferences without overwriting later per-device changes."""
    source = _add_legacy_entry(hass)
    candidate = device()
    identifier = candidate.device_info.mac
    old_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id, identifiers={(DOMAIN, identifier)}
    )
    old_entity = entity_registry.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        identifier,
        config_entry=source,
        device_id=old_device.id,
    )
    hass.config_entries.async_update_entry(
        source, pref_disable_polling=True, pref_disable_new_entities=True
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = result["result"]

    assert entry.pref_disable_polling
    assert entry.pref_disable_new_entities
    assert entity_registry.async_get(old_entity.entity_id).disabled_by is None
    light_entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{identifier}_Panel Light"
    )
    assert light_entity_id is not None
    assert (
        entity_registry.async_get(light_entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(light_entity_id) is None
    candidate.update_state.reset_mock()
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    candidate.update_state.assert_not_awaited()

    hass.config_entries.async_update_entry(
        entry, pref_disable_polling=False, pref_disable_new_entities=False
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not entry.pref_disable_polling
    assert not entry.pref_disable_new_entities
    candidate.update_state.reset_mock()
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    candidate.update_state.assert_awaited_once()
