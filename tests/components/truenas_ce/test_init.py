"""Unit tests for __init__.py (setup/unload, entity cleanup, service handlers).

Most helpers here are pure functions tested with bare mocks/``SimpleNamespace``,
like test_coordinator.py and test_migration.py. ``async_setup``/
``async_setup_entry``/``async_unload_entry`` go through the real ``hass``
fixture and ``MockConfigEntry`` instead, since they are HA's own config-entry
lifecycle entrypoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import truenas_ce as init_module
from homeassistant.components.truenas_ce import (
    _build_disabled_data_paths,
    _collect_active_unique_ids,
    _force_entity_unit,
    _handle_alert_dismiss,
    _handle_alert_list,
    _handle_alert_restore,
    _handle_keyless,
    _handle_passphrase_list,
    _handle_passphrase_remove,
    _migrate_data_size_units,
    _migrate_description,
    _process_dynamic_description,
    _process_static_description,
    _referenced_unique_ids,
    _require_config_entry,
    _resolve_config_entry,
)
from homeassistant.components.truenas_ce.const import (
    CONF_DATASET_PASSPHRASES,
    DOMAIN,
    MONITOR_GROUP_VMS,
    SERVICE_ALERT_DISMISS,
    SERVICE_ALERT_LIST,
    SERVICE_ALERT_PROPERTIES,
    SERVICE_ALERT_RESTORE,
    SERVICE_ALERT_UUID,
    SERVICE_PASSPHRASE_DATASET_PATH,
    SERVICE_PASSPHRASE_LIST,
    SERVICE_PASSPHRASE_REMOVE,
)
from homeassistant.components.truenas_ce.helper import scaled_data_unit
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def _desc(**kwargs: Any) -> TrueNASSensorEntityDescription:
    kwargs.setdefault("name", None)
    return TrueNASSensorEntityDescription(**kwargs)


def _config_entry(
    *,
    entry_id: str = "entry1",
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id=entry_id,
        data={CONF_NAME: "TrueNAS", **(data or {})},
        options=options or {},
        state=init_module.ConfigEntryState.LOADED,
    )


# ---------------------------
#   _migrate_data_size_units / _force_entity_unit
# ---------------------------
def test_force_entity_unit_writes_new_unit_option() -> None:
    """A newly computed unit that differs from the stored option triggers an update."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = "sensor.truenas_pool_usage"
    # Existing option ("MB") must differ from the newly-computed unit ("GB" for
    # 5e9 bytes decimal) so the update branch actually fires.
    existing_entry = SimpleNamespace(options={"sensor": {"unit_of_measurement": "MB"}})
    ent_reg.async_get.return_value = existing_entry
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 5_000_000_000, False)

    ent_reg.async_update_entity_options.assert_called_once()
    entity_id, domain, options = ent_reg.async_update_entity_options.call_args.args
    assert entity_id == "sensor.truenas_pool_usage"
    assert domain == "sensor"
    assert options["unit_of_measurement"] == "GB"


def test_force_entity_unit_noop_when_entity_missing() -> None:
    """No update happens when the entity id can't be resolved from the unique id."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = None
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 100, False)

    ent_reg.async_update_entity_options.assert_not_called()


def test_force_entity_unit_noop_when_unit_unchanged() -> None:
    """No update happens when the computed unit already matches the stored option."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = "sensor.truenas_pool_usage"
    # Pre-set the option to whatever scaled_data_unit will compute for value=0.
    unit, _ = scaled_data_unit(0, False)
    existing_entry = SimpleNamespace(options={"sensor": {"unit_of_measurement": unit}})
    ent_reg.async_get.return_value = existing_entry
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 0, False)

    ent_reg.async_update_entity_options.assert_not_called()


def test_migrate_data_size_units_processes_data_size_descriptions() -> None:
    """Migration processes every DATA_SIZE description found in the coordinator's data."""
    coordinator = MagicMock()
    coordinator.ds = {"pool": {"pool1": {"size": 5_000_000_000}}}
    entry = _config_entry(options={"data_unit": "GiB"})

    with (
        patch.object(init_module.er, "async_get", return_value=MagicMock()),
        patch.object(init_module, "_migrate_description") as migrate_mock,
    ):
        _migrate_data_size_units(MagicMock(), entry, coordinator)

    # Called at least once for a DATA_SIZE sensor description (pool available/usage).
    assert migrate_mock.called


def test_migrate_description_noop_when_data_not_dict() -> None:
    """Migration is skipped when the description's data path isn't present as a dict."""
    coordinator = MagicMock()
    coordinator.ds = {}
    description = _desc(key="pool_size", data_path="pool", data_attribute="size")

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(MagicMock(), coordinator, "TrueNAS", description, False)

    force_mock.assert_not_called()


def test_migrate_description_without_reference_calls_once() -> None:
    """A description without ``data_reference`` triggers a single force-unit call."""
    coordinator = MagicMock()
    coordinator.ds = {"system_info": {"uptime_seconds": 12345}}
    description = _desc(
        key="uptime", data_path="system_info", data_attribute="uptime_seconds"
    )
    ent_reg = MagicMock()

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(ent_reg, coordinator, "TrueNAS", description, False)

    force_mock.assert_called_once_with(
        ent_reg, "TrueNAS", description, None, 12345, False
    )


def test_migrate_description_with_reference_skips_non_dict_vals() -> None:
    """Non-dict values under a referenced data path are skipped, dict ones are migrated."""
    coordinator = MagicMock()
    coordinator.ds = {
        "pool": {
            "pool1": {"name": "tank", "size": 100},
            "pool2": "not-a-dict",
            "pool3": {"size": 200},
        }
    }
    description = _desc(
        key="pool_size",
        data_path="pool",
        data_reference="name",
        data_attribute="size",
    )
    ent_reg = MagicMock()

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(ent_reg, coordinator, "TrueNAS", description, True)

    assert force_mock.call_count == 2
    force_mock.assert_any_call(ent_reg, "TrueNAS", description, "tank", 100, True)
    force_mock.assert_any_call(ent_reg, "TrueNAS", description, "pool3", 200, True)


# ---------------------------
#   _handle_keyless / _referenced_unique_ids
# ---------------------------
def test_handle_keyless_routes_to_live_bases_when_disabled() -> None:
    """A disabled group's keyless unique id is recorded as a live base only."""
    active: set[str] = set()
    live_bases: set[str] = set()
    _handle_keyless("truenas-uptime", True, active, live_bases)
    assert live_bases == {"truenas-uptime"}
    assert active == set()


def test_handle_keyless_routes_to_active_when_enabled() -> None:
    """An enabled group's keyless unique id is recorded as active."""
    active: set[str] = set()
    live_bases: set[str] = set()
    _handle_keyless("truenas-uptime", False, active, live_bases)
    assert active == {"truenas-uptime"}
    assert live_bases == set()


def test_referenced_unique_ids_builds_ids_for_each_object() -> None:
    """Builds one unique id per object, keyed by its reference field."""
    description = _desc(key="vm_status", data_reference="name", data_attribute="status")
    data = {
        "1": {"name": "vm1", "status": "RUNNING"},
        "2": {"name": "vm2", "status": "STOPPED"},
    }
    ids = _referenced_unique_ids("TrueNAS", description, data)
    assert ids == {
        init_module.format_unique_id("TrueNAS", "vm_status", "vm1"),
        init_module.format_unique_id("TrueNAS", "vm_status", "vm2"),
    }


def test_referenced_unique_ids_honors_exclude_when_requested() -> None:
    """Objects matching the exclude condition are dropped when ``honor_exclude`` is set."""
    description = _desc(
        key="if_rx",
        data_reference="name",
        data_attribute="rx",
        data_exclude=("link_up", False),
    )
    data = {
        "eth0": {"name": "eth0", "rx": 1, "link_up": True},
        "eth1": {"name": "eth1", "rx": 2, "link_up": False},
    }
    ids = _referenced_unique_ids("TrueNAS", description, data, honor_exclude=True)
    assert ids == {init_module.format_unique_id("TrueNAS", "if_rx", "eth0")}


def test_referenced_unique_ids_ignores_exclude_when_not_honored() -> None:
    """The exclude condition is ignored when ``honor_exclude`` is ``False``."""
    description = _desc(
        key="if_rx",
        data_reference="name",
        data_attribute="rx",
        data_exclude=("link_up", False),
    )
    data = {"eth1": {"name": "eth1", "rx": 2, "link_up": False}}
    ids = _referenced_unique_ids("TrueNAS", description, data, honor_exclude=False)
    assert ids == {init_module.format_unique_id("TrueNAS", "if_rx", "eth1")}


def test_referenced_unique_ids_falls_back_to_uid_when_reference_missing() -> None:
    """Falls back to the dict key when the reference field is absent from the object."""
    description = _desc(key="vm_status", data_reference="name", data_attribute="status")
    data = {"1": {"status": "RUNNING"}}
    ids = _referenced_unique_ids("TrueNAS", description, data)
    assert ids == {init_module.format_unique_id("TrueNAS", "vm_status", "1")}


# ---------------------------
#   _build_disabled_data_paths
# ---------------------------
def test_build_disabled_data_paths_returns_paths_of_unmonitored_groups() -> None:
    """Returns the data paths belonging to groups that aren't in the monitored list."""
    monitored = [
        g for g in init_module.DEFAULT_MONITORED_GROUPS if g != MONITOR_GROUP_VMS
    ]
    disabled = _build_disabled_data_paths(monitored)
    assert "vm" in disabled
    assert "container" not in disabled


def test_build_disabled_data_paths_empty_when_all_monitored() -> None:
    """Returns an empty set when every group is monitored."""
    disabled = _build_disabled_data_paths(init_module.DEFAULT_MONITORED_GROUPS)
    assert disabled == set()


# ---------------------------
#   _process_static_description
# ---------------------------
def test_process_static_description_keyless_enabled() -> None:
    """A keyless description in an enabled group is added to the active set."""
    description = _desc(
        key="uptime", data_path="system_info", data_attribute="uptime_seconds"
    )
    active: set[str] = set()
    live_bases: set[str] = set()
    _process_static_description(
        "TrueNAS", description, set(), False, active, live_bases, {"system_info": {}}
    )
    assert active == {init_module.format_unique_id("TrueNAS", "uptime")}


def test_process_static_description_keyless_disabled_group() -> None:
    """A keyless description in a disabled group is added to ``live_bases`` only."""
    description = _desc(key="vm_count", data_path="vm", data_attribute="count")
    active: set[str] = set()
    live_bases: set[str] = set()
    _process_static_description(
        "TrueNAS", description, {"vm"}, False, active, live_bases, {}
    )
    assert live_bases == {init_module.format_unique_id("TrueNAS", "vm_count")}
    assert active == set()


def test_process_static_description_referenced_no_data_and_enabled_returns_early() -> (
    None
):
    """A referenced description with no data yields neither an active nor a live-base id."""
    description = _desc(key="vm_status", data_path="vm", data_reference="name")
    active: set[str] = set()
    live_bases: set[str] = set()
    _process_static_description(
        "TrueNAS", description, set(), False, active, live_bases, {"vm": {}}
    )
    assert active == set()
    assert live_bases == set()


def test_process_static_description_referenced_with_data() -> None:
    """A referenced description with data adds both the object id and its live base."""
    description = _desc(key="vm_status", data_path="vm", data_reference="name")
    active: set[str] = set()
    live_bases: set[str] = set()
    data = {"vm": {"1": {"name": "vm1"}}}
    _process_static_description(
        "TrueNAS", description, set(), False, active, live_bases, data
    )
    assert active == {init_module.format_unique_id("TrueNAS", "vm_status", "vm1")}
    assert live_bases == {init_module.format_unique_id("TrueNAS", "vm_status")}


def test_process_static_description_referenced_disabled_group_keeps_live_base() -> None:
    """A disabled group's referenced description still records its live base, not active ids."""
    description = _desc(key="vm_status", data_path="vm", data_reference="name")
    active: set[str] = set()
    live_bases: set[str] = set()
    data = {"vm": {"1": {"name": "vm1"}}}
    _process_static_description(
        "TrueNAS", description, {"vm"}, False, active, live_bases, data
    )
    assert active == set()
    assert live_bases == {init_module.format_unique_id("TrueNAS", "vm_status")}


# ---------------------------
#   _process_dynamic_description
# ---------------------------
def test_process_dynamic_description_ignores_static_description() -> None:
    """Static (non-dynamic-keys) descriptions are ignored by the dynamic processor."""
    description = _desc(key="uptime", data_path="system_info")
    active, live_bases = _process_dynamic_description(
        "TrueNAS", description, {}, False, set()
    )
    assert active == set()
    assert live_bases == set()


def test_process_dynamic_description_disabled_group_returns_live_base_only() -> None:
    """A disabled group's dynamic description yields only its live base, no active ids."""
    description = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    active, live_bases = _process_dynamic_description(
        "TrueNAS",
        description,
        {"app_stats": {"a": {"app_name": "a"}}},
        False,
        {"app_stats"},
    )
    assert active == set()
    assert live_bases == {init_module.format_unique_id("TrueNAS", "app_stats")}


def test_process_dynamic_description_no_reference_or_composite() -> None:
    """Without a reference or composite key, only the live base is reported."""
    description = _desc(key="app_stats", data_path="app_stats", data_dynamic_keys=True)
    active, live_bases = _process_dynamic_description(
        "TrueNAS", description, {"app_stats": {"a": {}}}, False, set()
    )
    assert active == set()
    assert live_bases == {init_module.format_unique_id("TrueNAS", "app_stats")}


def test_process_dynamic_description_with_reference() -> None:
    """A dynamic description with a reference field yields an active id per object."""
    description = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    data = {"app_stats": {"a": {"app_name": "myapp"}}}
    active, _live_bases = _process_dynamic_description(
        "TrueNAS", description, data, False, set()
    )
    assert active == {init_module.format_unique_id("TrueNAS", "app_stats", "myapp")}


def test_process_dynamic_description_with_composite_references() -> None:
    """Composite references combine the sub-key and the nested field into one unique id."""
    description = _desc(
        key="app_net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="interface_name",
        data_composite_references=("networks", "interface_name"),
    )
    data = {"app_stats": {"a": {"networks": [{"interface_name": "eth0"}]}}}
    active, _live_bases = _process_dynamic_description(
        "TrueNAS", description, data, False, set()
    )
    assert active == {init_module.format_unique_id("TrueNAS", "app_net", "a::eth0")}


def test_process_dynamic_description_empty_sub_data_reports_no_live_base() -> None:
    """A momentarily empty domain must not be reported as live.

    "Live base with nothing active" means "every entity below it is an orphan",
    so returning the base here deleted all app_stats entities from the registry
    on every restart -- app.stats is simply not populated yet on the first poll.
    """
    description = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    active, live_bases = _process_dynamic_description(
        "TrueNAS", description, {"app_stats": {}}, False, set()
    )
    assert active == set()
    assert live_bases == set()


def test_process_dynamic_description_missing_data_path_reports_no_live_base() -> None:
    """Same rule when the domain key is absent altogether, not just empty."""
    description = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    active, live_bases = _process_dynamic_description(
        "TrueNAS", description, {}, False, set()
    )
    assert active == set()
    assert live_bases == set()


# ---------------------------
#   _collect_active_unique_ids (integration of the helpers above)
# ---------------------------
def test_collect_active_unique_ids_combines_static_and_dynamic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collects active/live-base ids from both static and dynamic descriptions together."""
    static_desc = _desc(
        key="uptime", data_path="system_info", data_attribute="uptime_seconds"
    )
    dynamic_desc = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    monkeypatch.setattr(init_module, "_ALL_DESCRIPTIONS", (static_desc, dynamic_desc))

    coordinator = MagicMock()
    coordinator.config_entry.options = {}
    coordinator.data = {
        "system_info": {},
        "app_stats": {"a": {"app_name": "myapp"}},
    }

    active, live_bases = _collect_active_unique_ids("TrueNAS", coordinator)

    assert init_module.format_unique_id("TrueNAS", "uptime") in active
    assert init_module.format_unique_id("TrueNAS", "app_stats", "myapp") in active
    assert init_module.format_unique_id("TrueNAS", "app_stats") in live_bases


def test_collect_active_unique_ids_empty_dynamic_domain_yields_no_live_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty dynamic domain leaves cleanup nothing to match against.

    Regression guard for the restart wipe: with an empty ``app_stats`` payload
    the collected result must contain neither active ids nor a live base, so
    ``_cleanup_orphaned_entities`` keeps the existing registry entries.
    """
    dynamic_desc = _desc(
        key="app_stats",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    monkeypatch.setattr(init_module, "_ALL_DESCRIPTIONS", (dynamic_desc,))

    coordinator = MagicMock()
    coordinator.config_entry.options = {}
    coordinator.data = {"app_stats": {}}

    active, live_bases = _collect_active_unique_ids("TrueNAS", coordinator)

    assert active == set()
    assert live_bases == set()


def test_collect_active_unique_ids_honors_behavior_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The remove-inactive-NIC behavior toggle excludes down interfaces from active ids."""
    description = _desc(
        key="if_rx",
        data_path="interface",
        data_reference="name",
        data_attribute="rx",
        data_exclude=("link_up", False),
    )
    monkeypatch.setattr(init_module, "_ALL_DESCRIPTIONS", (description,))

    coordinator = MagicMock()
    coordinator.config_entry.options = {
        init_module.CONF_BEHAVIORS: [init_module.BEHAVIOR_REMOVE_INACTIVE_NIC]
    }
    coordinator.data = {
        "interface": {"eth1": {"name": "eth1", "rx": 1, "link_up": False}}
    }

    active, _ = _collect_active_unique_ids("TrueNAS", coordinator)
    assert active == set()


# ---------------------------
#   _resolve_config_entry / _require_config_entry
# ---------------------------
def test_resolve_config_entry_by_explicit_id() -> None:
    """Resolves the entry matching an explicitly given entry id."""
    hass = MagicMock()
    entry = _config_entry(entry_id="entry1")
    hass.config_entries.async_entries.return_value = [entry]

    resolved, error = _resolve_config_entry(hass, "entry1")
    assert resolved is entry
    assert error == {}


def test_resolve_config_entry_by_explicit_id_skips_non_matching_entries() -> None:
    """Skips entries that don't match the given id and resolves the correct one."""
    hass = MagicMock()
    entry1 = _config_entry(entry_id="e1")
    entry2 = _config_entry(entry_id="e2")
    hass.config_entries.async_entries.return_value = [entry1, entry2]

    resolved, error = _resolve_config_entry(hass, "e2")
    assert resolved is entry2
    assert error == {}


def test_resolve_config_entry_explicit_id_not_loaded() -> None:
    """Returns an error when the explicitly given entry exists but isn't loaded."""
    hass = MagicMock()
    entry = _config_entry(entry_id="entry1")
    entry.state = init_module.ConfigEntryState.NOT_LOADED
    hass.config_entries.async_entries.return_value = [entry]

    resolved, error = _resolve_config_entry(hass, "entry1")
    assert resolved is None
    assert "not loaded" in error["error"]


def test_resolve_config_entry_explicit_id_not_found() -> None:
    """Returns a not-found error when no entry matches the given id."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    resolved, error = _resolve_config_entry(hass, "missing")
    assert resolved is None
    assert "not found" in error["error"]


def test_resolve_config_entry_no_entries_loaded() -> None:
    """Returns a no-instances error when there are no config entries at all."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    resolved, error = _resolve_config_entry(hass, None)
    assert resolved is None
    assert "No TrueNAS instances" in error["error"]


def test_resolve_config_entry_multiple_loaded_without_id() -> None:
    """Returns an ambiguous-selection error when multiple entries exist and none was specified."""
    hass = MagicMock()
    entry1 = _config_entry(entry_id="e1")
    entry2 = _config_entry(entry_id="e2")
    hass.config_entries.async_entries.return_value = [entry1, entry2]
    resolved, error = _resolve_config_entry(hass, None)
    assert resolved is None
    assert "Multiple TrueNAS instances" in error["error"]


def test_resolve_config_entry_single_loaded_without_id() -> None:
    """Resolves the single loaded entry automatically when no id was given."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    hass.config_entries.async_entries.return_value = [entry]
    resolved, error = _resolve_config_entry(hass, None)
    assert resolved is entry
    assert error == {}


def test_require_config_entry_raises_on_error() -> None:
    """Raises ``ServiceValidationError`` when no config entry could be resolved."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError):
        _require_config_entry(hass, None)


def test_require_config_entry_returns_entry_on_success() -> None:
    """Returns the resolved entry when resolution succeeds."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    hass.config_entries.async_entries.return_value = [entry]
    assert _require_config_entry(hass, "e1") is entry


# ---------------------------
#   Alert / passphrase service handlers
# ---------------------------
async def test_handle_alert_list_returns_all_when_error() -> None:
    """Returns an empty alert list plus an error when no config entry can be resolved."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    call = SimpleNamespace(data={})
    result = await _handle_alert_list(hass, call)
    assert result["alerts"] == []
    assert "error" in result


async def test_handle_alert_list_filters_default_properties() -> None:
    """Filters returned alert fields down to the default property set."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = SimpleNamespace(
        api=SimpleNamespace(
            query=AsyncMock(
                return_value=[
                    {"uuid": "u1", "level": "WARNING", "formatted": "msg", "extra": "x"}
                ]
            )
        )
    )
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={})

    result = await _handle_alert_list(hass, call)

    # DEFAULT_ALERT_PROPERTIES is "uuid,formatted" -- level/extra are dropped.
    assert result["alerts"] == [{"uuid": "u1", "formatted": "msg"}]


async def test_handle_alert_list_returns_raw_with_wildcard() -> None:
    """Returns the raw alert dicts unfiltered when the wildcard property is requested."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    raw_alerts = [{"uuid": "u1", "level": "WARNING"}]
    entry.runtime_data = SimpleNamespace(
        api=SimpleNamespace(query=AsyncMock(return_value=raw_alerts))
    )
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_ALERT_PROPERTIES: "*"})

    result = await _handle_alert_list(hass, call)
    assert result == {"alerts": raw_alerts}


async def test_handle_alert_list_malformed_response() -> None:
    """Returns an empty list plus an error when the API response is malformed."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = SimpleNamespace(
        api=SimpleNamespace(query=AsyncMock(return_value=None))
    )
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={})

    result = await _handle_alert_list(hass, call)
    assert result["alerts"] == []
    assert "error" in result


async def test_handle_alert_dismiss_requires_uuid() -> None:
    """Raises ``ServiceValidationError`` when no alert uuid is supplied for dismiss."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={})

    with pytest.raises(ServiceValidationError) as exc_info:
        await _handle_alert_dismiss(hass, call)
    assert exc_info.value.translation_key == "missing_alert_uuid"
    assert exc_info.value.translation_placeholders == {"action": "dismiss"}


async def test_handle_alert_dismiss_calls_alert_action() -> None:
    """Dispatches the dismiss action to ``alert_action`` with the given uuid."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_ALERT_UUID: "u1"})

    with patch.object(init_module, "alert_action", new=AsyncMock()) as action_mock:
        await _handle_alert_dismiss(hass, call)

    action_mock.assert_awaited_once_with(entry.runtime_data, "u1", "dismiss")


async def test_handle_alert_restore_calls_alert_action() -> None:
    """Dispatches the restore action to ``alert_action`` with the given uuid."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_ALERT_UUID: "u1"})

    with patch.object(init_module, "alert_action", new=AsyncMock()) as action_mock:
        await _handle_alert_restore(hass, call)

    action_mock.assert_awaited_once_with(entry.runtime_data, "u1", "restore")


async def test_handle_alert_restore_requires_uuid() -> None:
    """Raises ``ServiceValidationError`` when no alert uuid is supplied for restore."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    entry.runtime_data = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={})

    with pytest.raises(ServiceValidationError) as exc_info:
        await _handle_alert_restore(hass, call)
    assert exc_info.value.translation_key == "missing_alert_uuid"
    assert exc_info.value.translation_placeholders == {"action": "restore"}


async def test_handle_passphrase_remove_requires_path() -> None:
    """Raises ``ServiceValidationError`` when the dataset path is blank."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1")
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_PASSPHRASE_DATASET_PATH: "  "})

    with pytest.raises(ServiceValidationError) as exc_info:
        await _handle_passphrase_remove(hass, call)
    assert exc_info.value.translation_key == "missing_dataset_path"


async def test_handle_passphrase_remove_requires_existing_entry() -> None:
    """Raises ``ServiceValidationError`` when no passphrase is stored for the given dataset."""
    hass = MagicMock()
    entry = _config_entry(entry_id="e1", data={CONF_DATASET_PASSPHRASES: {}})
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_PASSPHRASE_DATASET_PATH: "tank/data"})

    with pytest.raises(ServiceValidationError) as exc_info:
        await _handle_passphrase_remove(hass, call)
    assert exc_info.value.translation_key == "passphrase_not_found"
    assert exc_info.value.translation_placeholders == {"dataset": "tank/data"}


async def test_handle_passphrase_remove_deletes_entry() -> None:
    """Removes only the targeted dataset's passphrase, keeping the others intact."""
    hass = MagicMock()
    entry = _config_entry(
        entry_id="e1",
        data={CONF_DATASET_PASSPHRASES: {"tank/data": "secret", "tank/other": "x"}},
    )
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={SERVICE_PASSPHRASE_DATASET_PATH: "tank/data"})

    await _handle_passphrase_remove(hass, call)

    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert "tank/data" not in kwargs["data"][CONF_DATASET_PASSPHRASES]
    assert "tank/other" in kwargs["data"][CONF_DATASET_PASSPHRASES]


async def test_handle_passphrase_list_returns_sorted_dataset_names() -> None:
    """Returns the stored dataset names sorted alphabetically."""
    hass = MagicMock()
    entry = _config_entry(
        entry_id="e1", data={CONF_DATASET_PASSPHRASES: {"tank/b": "x", "tank/a": "y"}}
    )
    hass.config_entries.async_entries.return_value = [entry]
    call = SimpleNamespace(data={})

    result = await _handle_passphrase_list(hass, call)
    assert result == {"datasets": ["tank/a", "tank/b"]}


async def test_handle_passphrase_list_error_when_no_entry() -> None:
    """Returns an empty list plus an error when no config entry can be resolved."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    call = SimpleNamespace(data={})

    result = await _handle_passphrase_list(hass, call)
    assert result["datasets"] == []
    assert "error" in result


# ---------------------------
#   async_setup
# ---------------------------
async def test_async_setup_registers_all_services(hass: HomeAssistant) -> None:
    """``async_setup`` registers every one of the integration's five services."""
    assert await async_setup_component(hass, DOMAIN, {})

    for service in (
        SERVICE_ALERT_DISMISS,
        SERVICE_ALERT_RESTORE,
        SERVICE_ALERT_LIST,
        SERVICE_PASSPHRASE_REMOVE,
        SERVICE_PASSPHRASE_LIST,
    ):
        assert hass.services.has_service(DOMAIN, service)


# ---------------------------
#   async_setup_entry / async_unload_entry
# ---------------------------
async def test_async_setup_entry_wires_coordinator_and_platforms(
    hass: HomeAssistant,
) -> None:
    """Entry setup creates the coordinator, forwards platforms, and runs migration/adoption steps."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())

    with (
        patch.object(init_module, "TrueNASCoordinator", return_value=coordinator),
        patch.object(
            init_module, "async_adopt_legacy_entities", new=AsyncMock(return_value=[])
        ),
        patch.object(init_module, "_migrate_data_size_units") as migrate_mock,
        patch.object(init_module, "finalize_legacy_adoption") as finalize_mock,
        patch.object(init_module, "async_notify_migration_result") as notify_mock,
        patch.object(init_module, "register_system_device") as register_device_mock,
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.runtime_data is coordinator
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    migrate_mock.assert_called_once()
    finalize_mock.assert_called_once()
    notify_mock.assert_called_once()
    register_device_mock.assert_called_once_with(hass, entry, coordinator)
    assert coordinator.system_device_id is register_device_mock.return_value


async def test_async_setup_entry_refresh_listener_dispatches_update_signal(
    hass: HomeAssistant,
) -> None:
    """The coordinator's refresh listener dispatches the update-sensors signal."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())

    with (
        patch.object(init_module, "TrueNASCoordinator", return_value=coordinator),
        patch.object(
            init_module, "async_adopt_legacy_entities", new=AsyncMock(return_value=[])
        ),
        patch.object(init_module, "_migrate_data_size_units"),
        patch.object(init_module, "finalize_legacy_adoption"),
        patch.object(init_module, "async_notify_migration_result"),
        patch.object(init_module, "register_system_device"),
        patch.object(init_module, "async_dispatcher_send") as dispatch_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        refresh_callback = coordinator.async_add_listener.call_args.args[0]
        refresh_callback()

    dispatch_mock.assert_called_once_with(
        hass, init_module.SIGNAL_UPDATE_SENSORS, coordinator
    )


async def test_async_unload_entry_stops_coordinator_on_success(
    hass: HomeAssistant,
) -> None:
    """Unloading stops app-stats polling and closes the API connection on success."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, init_module.ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    coordinator = SimpleNamespace(
        stop_app_stats=AsyncMock(),
        api=SimpleNamespace(close=AsyncMock()),
    )
    entry.runtime_data = coordinator

    with patch.object(init_module, "get_truenas_coordinator", return_value=coordinator):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
    coordinator.stop_app_stats.assert_awaited_once()
    coordinator.api.close.assert_awaited_once()
    assert not hasattr(entry, "runtime_data")


async def test_async_unload_entry_noop_when_platform_unload_fails(
    hass: HomeAssistant,
) -> None:
    """Unload leaves the coordinator's ``runtime_data`` intact when platform unload fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, init_module.ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry.runtime_data = MagicMock()

    result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is False
    assert hasattr(entry, "runtime_data")


async def test_async_unload_entry_handles_missing_coordinator(
    hass: HomeAssistant,
) -> None:
    """Unload succeeds even when no coordinator is found for the entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, init_module.ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    with patch.object(init_module, "get_truenas_coordinator", return_value=None):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
