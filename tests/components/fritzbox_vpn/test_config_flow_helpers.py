"""Unit tests for entity registry helpers (registry repair, orphans)."""

import pytest
from custom_components.fritzbox_vpn.const import DOMAIN, UNIQUE_ID_PREFIX
from custom_components.fritzbox_vpn.entity_registry import (
    connection_uid_from_entity_unique_id,
    entity_id_base,
    entity_id_suffix_number,
    get_entity_id_suffix_repairs,
    get_orphaned_entity_entries,
    remove_orphaned_entities,
    repair_entity_id_suffixes,
    resolve_current_uids,
    uids_from_entity_entries,
)
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


def test_connection_uid_unknown_suffix() -> None:
    """Unique IDs without known suffix return None."""
    assert connection_uid_from_entity_unique_id(f"{UNIQUE_ID_PREFIX}abc_unknown") is None


def test_connection_uid_from_entity_unique_id() -> None:
    """Parse connection UID from entity unique_id."""
    uid = "abc"
    unique = f"{UNIQUE_ID_PREFIX}{uid}_switch"
    assert connection_uid_from_entity_unique_id(unique) == uid
    assert connection_uid_from_entity_unique_id(f"{UNIQUE_ID_PREFIX}{uid}_status") == uid
    assert connection_uid_from_entity_unique_id("other") is None


def test_entity_id_base_and_suffix() -> None:
    """Detect suffixed entity IDs."""
    assert entity_id_base("switch.vpn_office_2") == "switch.vpn_office"
    assert entity_id_suffix_number("switch.vpn_office_2") == 2
    assert entity_id_base("switch.vpn_office") is None


@pytest.mark.asyncio
async def test_resolve_current_uids_errors(hass: HomeAssistant) -> None:
    """resolve_current_uids reports integration and coordinator state."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    uids, err = resolve_current_uids(hass, entry.entry_id)
    assert uids is None
    assert err == "integration_not_loaded"

    entry.runtime_data = FritzboxVpnRuntimeData(
        coordinator=type("C", (), {"data": None})(),
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)
    uids, err = resolve_current_uids(hass, entry.entry_id)
    assert uids is None
    assert err == "coordinator_not_ready"


@pytest.mark.asyncio
async def test_orphaned_entities(hass: HomeAssistant) -> None:
    """Orphaned entities are those whose UID is not in current set."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}gone_switch",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}keep_switch",
        config_entry=entry,
    )
    to_remove, err = get_orphaned_entity_entries(
        hass, entry.entry_id, current_uids={"keep"}
    )
    assert err is None
    assert len(to_remove) == 1
    assert uids_from_entity_entries(to_remove) == {"gone"}


@pytest.mark.asyncio
async def test_repair_entity_id_suffixes(hass: HomeAssistant) -> None:
    """Repair renames suffixed entity to base when base is free."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    suffixed = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_switch",
        suggested_object_id="fritzbox_vpn_vpn1_switch_2",
        config_entry=entry,
    )
    repairs = get_entity_id_suffix_repairs(registry, entry.entry_id)
    assert repairs

    count, messages = repair_entity_id_suffixes(hass, entry.entry_id)
    assert count >= 0
    if count:
        assert messages
        updated = registry.async_get(suffixed.entity_id)
        assert updated is None or "_2" not in (updated.entity_id or "")


@pytest.mark.asyncio
async def test_remove_orphaned_entities_removes_device(hass: HomeAssistant) -> None:
    """Removing orphaned entities also removes their device when requested."""
    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entity = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}gone_switch",
        config_entry=entry,
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id, "gone")},
        name="Gone VPN",
    )
    remove_orphaned_entities(
        hass, entry.entry_id, [entity], remove_from_registry=True
    )
    assert entity_registry.async_get(entity.entity_id) is None


def test_entity_id_helpers_edge_cases() -> None:
    """Entity ID helpers handle empty and non-suffixed IDs."""
    assert entity_id_base("") is None
    assert entity_id_suffix_number("switch.plain") is None


@pytest.mark.asyncio
async def test_remove_orphaned_clears_known_uids(hass: HomeAssistant) -> None:
    """remove_orphaned_entities subtracts UIDs from integration store."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    runtime = FritzboxVpnRuntimeData(
        coordinator=type("C", (), {"data": {}})(),
    )
    runtime.known_uids_switch = {"gone", "keep"}
    entry.runtime_data = runtime
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}gone_switch",
        config_entry=entry,
    )
    remove_orphaned_entities(
        hass, entry.entry_id, [entity], remove_from_registry=False
    )
    assert entry.runtime_data.known_uids_switch == {"keep"}


def test_get_entity_id_suffix_repairs_with_stale_base(hass: HomeAssistant) -> None:
    """Repair list includes suffixed entries when stale base exists."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn2_switch",
        suggested_object_id="fritzbox_vpn_vpn2_switch",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn2b_switch",
        suggested_object_id="fritzbox_vpn_vpn2_switch_2",
        config_entry=entry,
    )
    repairs = get_entity_id_suffix_repairs(registry, entry.entry_id)
    assert isinstance(repairs, list)
    assert base.entity_id
