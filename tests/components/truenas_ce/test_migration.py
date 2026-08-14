"""Registry-mutation coverage for migration.py.

``async_adopt_legacy_entities``/``finalize_legacy_adoption``/``_remap_and_restore``/
``async_rollback_to_legacy`` mutate a real
``homeassistant.helpers.entity_registry.EntityRegistry`` (renames, permutation-safe
swaps, removals) -- a bare-instance/``SimpleNamespace`` hass (used elsewhere in this
suite, see test_coordinator.py/test_init.py) would not exercise any of that, so this
follows test_entity_setup.py's real-``hass`` style instead.
"""

from __future__ import annotations

from homeassistant.components.truenas_ce.const import (
    DOMAIN,
    LEGACY_DOMAIN,
    MIGRATION_DONE,
)
from homeassistant.components.truenas_ce.migration import (
    _R_AREA,
    _R_DISABLED,
    _R_ENTITY_DOMAIN,
    _R_ENTITY_ID,
    _R_ICON,
    _R_NAME,
    _R_UNIQUE_ID,
    _find_legacy_entry,
    _remap_and_restore,
    async_adopt_legacy_entities,
    async_rollback_to_legacy,
    finalize_legacy_adoption,
    pending_legacy_records,
)
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


# ---------------------------
#   _find_legacy_entry
# ---------------------------
def test_find_legacy_entry_matches_by_host(hass: HomeAssistant) -> None:
    """A legacy entry with the exact same host is found."""
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})

    assert _find_legacy_entry(hass, new_entry) is legacy


def test_find_legacy_entry_ignores_unrelated_host(hass: HomeAssistant) -> None:
    """Regression test: a lone legacy entry for a *different* box must not be adopted.

    A previous "single legacy entry -> adopt regardless of host" fallback also
    fired for "migrate manually" and for a plain new entry, disabling and
    stripping an unrelated legacy entry's entities.
    """
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "other-nas.local"})
    legacy.add_to_hass(hass)
    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})

    assert _find_legacy_entry(hass, new_entry) is None


# ---------------------------
#   forward adoption / finalize
# ---------------------------
async def test_forward_adoption_frees_and_reattaches_entity_id(
    hass: HomeAssistant,
) -> None:
    """A legacy entity's id is freed on adoption and reclaimed once matched.

    Once the matching new entity is created, recorder history reconnects.
    """
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    legacy_entity = ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)

    records = await async_adopt_legacy_entities(hass, new_entry)

    assert len(records) == 1
    assert ent_reg.async_get(legacy_entity.entity_id) is None
    assert legacy.disabled_by == ConfigEntryDisabler.USER
    assert new_entry.data[MIGRATION_DONE] is True

    # The new platform creates its entity under the same unique_id, but at a
    # fresh, unrelated auto-assigned entity_id.
    new_entity = ent_reg.async_get_or_create(
        "sensor", DOMAIN, "uptime-uid", config_entry=new_entry
    )
    assert new_entity.entity_id != legacy_entity.entity_id

    finalize_legacy_adoption(hass, new_entry, records)

    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, "uptime-uid")
        == legacy_entity.entity_id
    )


async def test_second_setup_is_idempotent_noop(hass: HomeAssistant) -> None:
    """A second ``async_adopt_legacy_entities`` call must not re-adopt anything."""
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)
    await async_adopt_legacy_entities(hass, new_entry)

    assert await async_adopt_legacy_entities(hass, new_entry) == []


# ---------------------------
#   pending_legacy_records
# ---------------------------
async def test_pending_record_reclaims_id_once_entity_later_appears(
    hass: HomeAssistant,
) -> None:
    """A record whose entity does not exist yet at first setup must retry.

    E.g. a disabled monitored group -- it must still reclaim its id once
    that entity is later created, without requiring a fresh adoption.
    """
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    legacy_entity = ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "vm-uid", config_entry=legacy
    )

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)
    records = await async_adopt_legacy_entities(hass, new_entry)
    finalize_legacy_adoption(
        hass, new_entry, records
    )  # no matching new entity yet -> no-op

    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "vm-uid") is None
    assert len(pending_legacy_records(hass, new_entry)) == 1

    # The object reappears (or its monitored group is re-enabled) and the
    # platform finally creates the matching entity.
    ent_reg.async_get_or_create("sensor", DOMAIN, "vm-uid", config_entry=new_entry)
    finalize_legacy_adoption(hass, new_entry, pending_legacy_records(hass, new_entry))

    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, "vm-uid")
        == legacy_entity.entity_id
    )
    assert pending_legacy_records(hass, new_entry) == []


async def test_pending_legacy_records_excludes_resolved_and_diverged(
    hass: HomeAssistant,
) -> None:
    """An already-resolved (or since manually renamed) record must not return.

    Regression guard: re-including it would let a later retry fight the
    user's rename.
    """
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)
    records = await async_adopt_legacy_entities(hass, new_entry)
    ent_reg.async_get_or_create("sensor", DOMAIN, "uptime-uid", config_entry=new_entry)
    finalize_legacy_adoption(hass, new_entry, records)

    assert pending_legacy_records(hass, new_entry) == []

    resolved_entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "uptime-uid")
    assert resolved_entity_id is not None
    ent_reg.async_update_entity(resolved_entity_id, new_entity_id="sensor.custom_name")

    assert pending_legacy_records(hass, new_entry) == []


# ---------------------------
#   _remap_and_restore (permutation-safe swap)
# ---------------------------
def test_remap_and_restore_handles_swapped_ids(hass: HomeAssistant) -> None:
    """Two entities whose target ids form a swap must both reach their target.

    E.g. re-lettered ``sd*`` disks, without a transient collision.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)

    entity_a = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "disk-a-uid",
        config_entry=entry,
        suggested_object_id="disk_a",
    )
    entity_b = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "disk-b-uid",
        config_entry=entry,
        suggested_object_id="disk_b",
    )
    assert entity_a.entity_id == "sensor.disk_a"
    assert entity_b.entity_id == "sensor.disk_b"

    def _record(unique_id: str, target_entity_id: str) -> dict[str, object]:
        return {
            _R_UNIQUE_ID: unique_id,
            _R_ENTITY_DOMAIN: "sensor",
            _R_ENTITY_ID: target_entity_id,
            _R_NAME: None,
            _R_ICON: None,
            _R_AREA: None,
            _R_DISABLED: False,
        }

    pairs = [
        ("sensor.disk_a", "sensor.disk_b", _record("disk-a-uid", "sensor.disk_b")),
        ("sensor.disk_b", "sensor.disk_a", _record("disk-b-uid", "sensor.disk_a")),
    ]
    _remap_and_restore(ent_reg, pairs)

    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, "disk-a-uid") == "sensor.disk_b"
    )
    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, "disk-b-uid") == "sensor.disk_a"
    )


# ---------------------------
#   async_rollback_to_legacy
# ---------------------------
async def test_rollback_returns_false_without_a_migration(hass: HomeAssistant) -> None:
    """An entry that never adopted anything has nothing to roll back."""
    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)

    assert await async_rollback_to_legacy(hass, new_entry) is False


async def test_rollback_returns_false_when_legacy_entry_already_gone(
    hass: HomeAssistant,
) -> None:
    """Rollback is impossible once the legacy entry itself was deleted."""
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)
    await async_adopt_legacy_entities(hass, new_entry)

    await hass.config_entries.async_remove(legacy.entry_id)

    assert await async_rollback_to_legacy(hass, new_entry) is False


async def test_rollback_removes_entry_reenables_legacy_and_restores_id(
    hass: HomeAssistant,
) -> None:
    """A full rollback removes the CE entry, re-enables and restores legacy."""
    legacy = MockConfigEntry(domain=LEGACY_DOMAIN, data={CONF_HOST: "nas.local"})
    legacy.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    legacy_entity = ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )
    original_legacy_id = legacy_entity.entity_id

    new_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "nas.local"})
    new_entry.add_to_hass(hass)
    records = await async_adopt_legacy_entities(hass, new_entry)
    ent_reg.async_get_or_create("sensor", DOMAIN, "uptime-uid", config_entry=new_entry)
    finalize_legacy_adoption(hass, new_entry, records)
    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, "uptime-uid")
        == original_legacy_id
    )

    # Simulate the legacy integration recreating its entity once re-enabled:
    # its original id is still held by the truenas_ce entity at this point, so
    # it lands on a fresh one, exactly like a real platform setup would.
    recreated = ent_reg.async_get_or_create(
        "sensor", LEGACY_DOMAIN, "uptime-uid", config_entry=legacy
    )
    assert recreated.entity_id != original_legacy_id

    result = await async_rollback_to_legacy(hass, new_entry)

    assert result is True
    assert hass.config_entries.async_get_entry(new_entry.entry_id) is None
    assert legacy.disabled_by is None
    assert (
        ent_reg.async_get_entity_id("sensor", LEGACY_DOMAIN, "uptime-uid")
        == original_legacy_id
    )
