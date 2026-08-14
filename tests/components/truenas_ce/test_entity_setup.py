"""Real-``hass`` coverage for entity.py's platform-setup wiring.

``_cleanup_orphaned_entities`` and ``async_add_entities`` both need a real
entity/device registry (``er.async_get``/``dr.async_get``) and, for
``async_add_entities``, the ``entity_platform`` context var that only exists
while a platform's own ``async_setup_entry`` is actually running -- none of
this can be faked with a bare-instance/``SimpleNamespace`` coordinator, unlike
most of this test suite.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components import truenas_ce as init_module
from homeassistant.components.truenas_ce.const import (
    CONF_MONITORED_GROUPS,
    DOMAIN,
    GROUP_DATA_PATHS,
    MONITOR_GROUP_SNAPSHOTS,
)
from homeassistant.components.truenas_ce.entity import (
    _cleanup_orphaned_entities,
    format_unique_id,
)
from homeassistant.components.truenas_ce.sensor_types import SENSOR_TYPES
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


# ---------------------------
#   _cleanup_orphaned_entities
# ---------------------------
async def test_cleanup_orphaned_entities_removes_stale_entity_and_empty_device(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"})
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(last_update_success=True)

    dev_reg = dr.async_get(hass)
    live_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "live-device")}
    )
    empty_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "empty-device")}
    )

    ent_reg = er.async_get(hass)
    active_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "truenas-active-id",
        config_entry=entry,
        device_id=live_device.id,
    )
    orphan_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "truenas-live-base-orphan",
        config_entry=entry,
        device_id=empty_device.id,
    )
    unrelated_entity = ent_reg.async_get_or_create(
        "sensor", DOMAIN, "truenas-unrelated-id", config_entry=entry
    )

    with patch.object(
        init_module,
        "_collect_active_unique_ids",
        return_value=({"truenas-active-id"}, {"truenas-live-base"}),
    ):
        _cleanup_orphaned_entities(hass, entry, coordinator)

    assert ent_reg.async_get(active_entity.entity_id) is not None
    assert ent_reg.async_get(orphan_entity.entity_id) is None
    assert ent_reg.async_get(unrelated_entity.entity_id) is not None
    assert dev_reg.async_get(live_device.id) is not None
    assert dev_reg.async_get(empty_device.id) is None


async def test_cleanup_orphaned_entities_noop_after_failed_refresh(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"})
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(last_update_success=False)

    ent_reg = er.async_get(hass)
    stale_entity = ent_reg.async_get_or_create(
        "sensor", DOMAIN, "truenas-live-base-orphan", config_entry=entry
    )

    with patch.object(init_module, "_collect_active_unique_ids") as collect_mock:
        _cleanup_orphaned_entities(hass, entry, coordinator)
    collect_mock.assert_not_called()
    assert ent_reg.async_get(stale_entity.entity_id) is not None


async def test_cleanup_keeps_entities_when_dynamic_domain_is_empty(
    hass: HomeAssistant,
) -> None:
    """An empty ``app_stats`` payload must not wipe the app-stats entities.

    ``app.stats`` is a subscription-fed domain: right after a restart the
    coordinator has no sample yet, so the whole domain is legitimately empty
    for one poll. Running the real ``_collect_active_unique_ids`` here (not a
    patched one) is the point of this test -- it is the collection step that
    used to report the base as live and hand cleanup a full set of "orphans".
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"})
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(
        last_update_success=True,
        config_entry=entry,
        data={"app_stats": {}},
    )

    ent_reg = er.async_get(hass)
    app_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        format_unique_id("TrueNAS", "app_stats_cpu", "myapp"),
        config_entry=entry,
    )

    _cleanup_orphaned_entities(hass, entry, coordinator)

    assert ent_reg.async_get(app_entity.entity_id) is not None


# ---------------------------
#   async_add_entities (via a real platform-setup pass)
# ---------------------------
def _fake_api(extra_responses: dict[str, Any] | None = None) -> SimpleNamespace:
    """A fake TrueNASAPI returning an empty (but present) system.info payload.

    Every other query returns None -- matching the coordinator's normal
    handling of a not-yet-responding TrueNAS -- unless ``extra_responses``
    overrides it for a specific method. The coordinator's core jobs (disk,
    scrub, app, alerts, certificates, arc, smb, pool, update-check, ...) run
    unconditionally every update regardless of monitored groups, so a caller
    only needs to override the one query it actually cares about; this keeps
    the platform-forward pass real while avoiding any actual network I/O.

    ``Any`` mirrors ``TrueNASAPI.query()``'s own return type -- per-method
    structural types aren't modelled here because production code (see
    ``apiparser.parse_api``) is deliberately defensive about API response
    shapes rather than trusting a fixed schema.
    """
    responses = extra_responses or {}

    async def _query(method: str, *args: object, **kwargs: object) -> Any:
        if method in responses:
            return responses[method]
        return {} if method == "system.info" else None

    return SimpleNamespace(
        connected=MagicMock(return_value=True),
        connect=AsyncMock(return_value=True),
        close=AsyncMock(),
        query=AsyncMock(side_effect=_query),
        error="",
        scheme="ws",
    )


async def test_async_setup_entry_creates_entities_via_real_platform_setup(
    hass: HomeAssistant,
) -> None:
    """A real ``async_setup_entry`` run forwards to every platform, so this
    exercises ``entity.async_add_entities``'s live wiring (service
    registration, dispatcher-connect, coordinator-identity check, entity
    creation) exactly as production does -- not reachable via a bare-instance
    coordinator since it needs the real ``entity_platform`` context var.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "test-key",
            CONF_VERIFY_SSL: False,
        },
        options={CONF_MONITORED_GROUPS: []},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=_fake_api(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids("sensor")


async def test_async_setup_entry_keeps_system_device_alive(
    hass: HomeAssistant,
) -> None:
    """Regression test: the System device must survive its own initial setup.

    ``register_system_device`` creates it before the sensor platform attaches
    any entity to it. Orphaned-entity/empty-device cleanup must only run
    *after* that attachment, or the empty-device branch deletes it
    immediately, leaving ``coordinator.system_device_id`` pointing at a
    device that no longer exists.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "test-key",
            CONF_VERIFY_SSL: False,
        },
        options={CONF_MONITORED_GROUPS: []},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=_fake_api(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    dev_reg = dr.async_get(hass)
    system_device = dev_reg.async_get(coordinator.system_device_id)
    assert system_device is not None
    assert er.async_entries_for_device(
        er.async_get(hass), system_device.id, include_disabled_entities=True
    )


async def test_async_setup_entry_creates_snapshottask_sensor_via_dispatcher(
    hass: HomeAssistant,
) -> None:
    """A description's ``func`` must have a matching dispatcher entry in its
    platform module -- a missing one raises ``KeyError`` and aborts that
    platform's entire setup (the ``TrueNASSnapshotTaskSensor`` regression).
    """
    snapshottask_row = {"id": 1, "dataset": "tank/data", "state": {"state": "PENDING"}}
    fake_api = _fake_api(
        extra_responses={"pool.snapshottask.query": [snapshottask_row]}
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "test-key",
            CONF_VERIFY_SSL: False,
        },
        options={CONF_MONITORED_GROUPS: [MONITOR_GROUP_SNAPSHOTS]},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=fake_api,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Same group -> data_path mapping production code uses for orphan-cleanup
    # (GROUP_DATA_PATHS), so this targets "the snapshot task description" by
    # the same identity the rest of the codebase does -- not by which sensor
    # class currently implements it.
    (snapshottask_data_path,) = GROUP_DATA_PATHS[MONITOR_GROUP_SNAPSHOTS]
    snapshottask_description = next(
        d for d in SENSOR_TYPES if d.data_path == snapshottask_data_path
    )
    ent_reg = er.async_get(hass)
    unique_id = format_unique_id("TrueNAS", snapshottask_description.key, 1)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None
