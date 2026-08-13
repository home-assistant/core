"""Unit tests for sensor.py."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.truenas_ce import sensor as sensor_mod
from homeassistant.components.truenas_ce.const import CONF_DATA_UNIT
from homeassistant.components.truenas_ce.sensor import (
    TrueNASAlertSensor,
    TrueNASAppStatsSensor,
    TrueNASCertExpirySensor,
    TrueNASCloudsyncSensor,
    TrueNASDatasetSensor,
    TrueNASDiskSensor,
    TrueNASReplicationSensor,
    TrueNASRsyncSensor,
    TrueNASSensor,
    TrueNASSnapshotTaskSensor,
    TrueNASUptimeSensor,
    _compose_app_network_uid,
    _discover_app_stats,
    _discover_network_sensors,
    _discover_standard_sensor,
    _maybe_discover_app_stats_sensor,
    _parse_app_network_uid,
    _resolve_app_network_data,
)
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.const import UnitOfInformation
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ._fakes import make_config_entry, make_coordinator

_PLAIN_DESC = TrueNASSensorEntityDescription(
    key="k", name="N", data_path="disk", data_attribute="value"
)


def _make_sensor(
    cls,
    data: dict,
    path: str = "disk",
    desc: TrueNASSensorEntityDescription | None = None,
):
    description = desc or TrueNASSensorEntityDescription(
        key="k", name="N", data_path=path, data_attribute="value"
    )
    coordinator = make_coordinator(data={path: {"o1": data}})
    return cls(coordinator, description, "o1")


# ---------------------------
#   _parse_app_network_uid / _compose_app_network_uid / _resolve_app_network_data
# ---------------------------
def test_compose_and_parse_roundtrip() -> None:
    uid = _compose_app_network_uid("plex", "eth0")
    assert uid == "plex::eth0"
    assert _parse_app_network_uid(uid) == ("plex", "eth0")


@pytest.mark.parametrize("uid", ["no-separator", "::eth0", "plex::", "::"])
def test_parse_app_network_uid_malformed_returns_none_none(uid: str) -> None:
    assert _parse_app_network_uid(uid) == (None, None)


def test_resolve_app_network_data_malformed_uid_returns_none() -> None:
    assert _resolve_app_network_data("bad-uid", {}) is None


def test_resolve_app_network_data_unknown_base_returns_none() -> None:
    assert _resolve_app_network_data("plex::eth0", {}) is None


def test_resolve_app_network_data_networks_not_list_returns_none() -> None:
    app_stats = {"plex": {"networks": "not-a-list"}}
    assert _resolve_app_network_data("plex::eth0", app_stats) is None


def test_resolve_app_network_data_no_matching_interface_returns_none() -> None:
    app_stats = {"plex": {"networks": [{"interface_name": "eth1"}]}}
    assert _resolve_app_network_data("plex::eth0", app_stats) is None


def test_resolve_app_network_data_returns_merged_payload() -> None:
    app_stats = {
        "plex": {"app_name": "plex", "networks": [{"interface_name": "eth0", "rx": 5}]}
    }
    result = _resolve_app_network_data("plex::eth0", app_stats)
    assert result == {
        "app_name": "plex",
        "networks": app_stats["plex"]["networks"],
        "interface_name": "eth0",
        "rx": 5,
    }


# ---------------------------
#   _discover_network_sensors / _discover_standard_sensor /
#   _maybe_discover_app_stats_sensor
# ---------------------------
def _net_desc(key: str = "app_stats_network_rx") -> TrueNASSensorEntityDescription:
    return TrueNASSensorEntityDescription(key=key, name="RX", data_path="app_stats")


def test_discover_network_sensors_ignores_non_list_networks() -> None:
    entities: list = []
    _discover_network_sensors(
        _net_desc(), "plex", {"networks": "bad"}, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_discover_network_sensors_ignores_non_dict_and_missing_name() -> None:
    entities: list = []
    app_data = {"networks": ["not-a-dict", {}, {"interface_name": ""}]}
    _discover_network_sensors(
        _net_desc(), "plex", app_data, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_discover_network_sensors_creates_entity_and_skips_loaded() -> None:
    entities: list = []
    app_data = {"networks": [{"interface_name": "eth0"}]}
    coord = make_coordinator()
    loaded: set[str] = set()
    _discover_network_sensors(
        _net_desc(), "plex", app_data, "TrueNAS", loaded, entities, coord
    )
    assert len(entities) == 1

    entities2: list = []
    _discover_network_sensors(
        _net_desc(), "plex", app_data, "TrueNAS", loaded, entities2, coord
    )
    assert not entities2


def test_discover_standard_sensor_creates_and_skips_loaded() -> None:
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu", name="CPU", data_path="app_stats"
    )
    entities: list = []
    coord = make_coordinator()
    loaded: set[str] = set()
    _discover_standard_sensor(desc, "plex", "TrueNAS", loaded, entities, coord)
    assert len(entities) == 1

    entities2: list = []
    _discover_standard_sensor(desc, "plex", "TrueNAS", loaded, entities2, coord)
    assert not entities2


def test_maybe_discover_app_stats_sensor_skips_empty_app_data() -> None:
    entities: list = []
    _maybe_discover_app_stats_sensor(
        _net_desc(), "plex", {}, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_maybe_discover_app_stats_sensor_routes_network_key() -> None:
    entities: list = []
    coord = make_coordinator()
    app_data = {"networks": [{"interface_name": "eth0"}]}
    _maybe_discover_app_stats_sensor(
        _net_desc(), "plex", app_data, "inst", set(), entities, coord
    )
    assert len(entities) == 1
    assert entities[0]._uid == "plex::eth0"


def test_maybe_discover_app_stats_sensor_routes_standard_key() -> None:
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu", name="CPU", data_path="app_stats"
    )
    entities: list = []
    coord = make_coordinator()
    _maybe_discover_app_stats_sensor(
        desc, "plex", {"cpu": 1}, "inst", set(), entities, coord
    )
    assert len(entities) == 1
    assert entities[0]._uid == "plex"


def test_discover_app_stats_adds_new_entities_via_callback() -> None:
    coord = make_coordinator(data={"app_stats": {"plex": {"cpu": 1}}})
    platform = SimpleNamespace(entities={})
    add_entities = MagicMock()
    with patch.object(
        sensor_mod,
        "_app_stats_descriptions",
        return_value=[
            TrueNASSensorEntityDescription(
                key="app_stats_cpu", name="CPU", data_path="app_stats"
            )
        ],
    ):
        _discover_app_stats(platform, coord, add_entities)
    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[0]) == 1


def test_discover_app_stats_no_entities_skips_callback() -> None:
    coord = make_coordinator(data={"app_stats": {}})
    platform = SimpleNamespace(entities={})
    add_entities = MagicMock()
    _discover_app_stats(platform, coord, add_entities)
    add_entities.assert_not_called()


# ---------------------------
#   TrueNASSensor
# ---------------------------
def test_native_value_returns_data_attribute() -> None:
    sensor = _make_sensor(TrueNASSensor, {"value": 42})
    assert sensor.native_value == 42


def test_native_unit_of_measurement_plain() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="MB",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor.native_unit_of_measurement == "MB"


def test_native_unit_of_measurement_none_when_not_configured() -> None:
    sensor = _make_sensor(TrueNASSensor, {"value": 1})
    assert sensor.native_unit_of_measurement is None


def test_native_unit_of_measurement_data_prefixed_present() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="data__uom",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1, "uom": "GB"}, desc=desc)
    assert sensor.native_unit_of_measurement == "GB"


def test_native_unit_of_measurement_data_prefixed_missing_falls_back() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="data__uom",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor.native_unit_of_measurement == "data__uom"


def test_init_scales_gib_suggested_unit_from_options() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    )
    entry = make_config_entry(options={CONF_DATA_UNIT: "GiB"})
    coordinator = make_coordinator(
        data={"disk": {"o1": {"value": 5 * 1024**3}}}, config_entry=entry
    )
    sensor = TrueNASSensor(coordinator, desc, "o1")
    assert sensor._attr_suggested_unit_of_measurement == UnitOfInformation.GIBIBYTES


def test_init_scales_gb_suggested_unit_from_entry_data_fallback() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    )
    entry = make_config_entry(data={CONF_DATA_UNIT: "GB"})
    coordinator = make_coordinator(
        data={"disk": {"o1": {"value": 5 * 1000**3}}}, config_entry=entry
    )
    sensor = TrueNASSensor(coordinator, desc, "o1")
    assert sensor._attr_suggested_unit_of_measurement == UnitOfInformation.GIGABYTES


def test_init_does_not_scale_non_gb_suggested_unit() -> None:
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement="MB/s",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor._attr_suggested_unit_of_measurement == "MB/s"


# ---------------------------
#   TrueNASCertExpirySensor
# ---------------------------
def test_cert_expiry_none_when_missing() -> None:
    sensor = _make_sensor(TrueNASCertExpirySensor, {})
    assert sensor.native_value is None


def test_cert_expiry_days_when_under_a_year() -> None:
    sensor = _make_sensor(TrueNASCertExpirySensor, {"value": 100})
    assert sensor.native_value == 100
    assert sensor.native_unit_of_measurement.value == "d"


def test_cert_expiry_years_when_over_a_year() -> None:
    sensor = _make_sensor(TrueNASCertExpirySensor, {"value": 730})
    assert sensor.native_value == 2.0
    assert sensor.native_unit_of_measurement.value == "y"


# ---------------------------
#   TrueNASDiskSensor
# ---------------------------
@pytest.mark.parametrize(
    ("devname", "disk_type", "expected"),
    [
        ("nvme0n1", "SSD", "mdi:expansion-card-variant"),
        ("sda", "HDD", "mdi:harddisk"),
        ("sda", "SSD", "mdi:chip"),
        ("sda", "SED", "mdi:chip"),
        ("sda", "WEIRD", "mdi:harddisk"),
    ],
)
def test_disk_sensor_icon(devname: str, disk_type: str, expected: str) -> None:
    sensor = _make_sensor(TrueNASDiskSensor, {"devname": devname, "type": disk_type})
    assert sensor.icon == expected


# ---------------------------
#   TrueNASUptimeSensor
# ---------------------------
def test_uptime_native_value_positive() -> None:
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 1735689600})
    assert isinstance(sensor.native_value, datetime)


def test_uptime_native_value_zero_is_none() -> None:
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 0})
    assert sensor.native_value is None


async def test_uptime_restart_calls_reboot() -> None:
    sensor = _make_sensor(TrueNASUptimeSensor, {})
    await sensor.restart()
    sensor.coordinator.api.query.assert_awaited_once_with(
        "system.reboot", ["Home Assistant Integration"]
    )


async def test_uptime_stop_calls_shutdown() -> None:
    sensor = _make_sensor(TrueNASUptimeSensor, {})
    await sensor.stop()
    sensor.coordinator.api.query.assert_awaited_once_with(
        "system.shutdown", ["Home Assistant Integration"]
    )


async def test_uptime_refresh_calls_coordinator_refresh() -> None:
    sensor = _make_sensor(TrueNASUptimeSensor, {})
    await sensor.refresh()
    sensor.coordinator.async_refresh.assert_awaited_once()


# ---------------------------
#   TrueNASAlertSensor
# ---------------------------
async def test_alert_dismiss_without_uuid_raises() -> None:
    sensor = _make_sensor(TrueNASAlertSensor, {})
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.dismiss()
    assert exc_info.value.translation_key == "missing_uuid"


async def test_alert_dismiss_with_uuid_calls_query_and_refreshes() -> None:
    sensor = _make_sensor(TrueNASAlertSensor, {})
    await sensor.dismiss(uuid="u1")
    sensor.coordinator.api.query.assert_awaited_once_with("alert.dismiss", ["u1"])
    sensor.coordinator.async_refresh.assert_awaited_once()


async def test_alert_restore_without_uuid_raises() -> None:
    sensor = _make_sensor(TrueNASAlertSensor, {})
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.restore()
    assert exc_info.value.translation_key == "missing_uuid"


async def test_alert_restore_with_uuid_calls_query_and_refreshes() -> None:
    sensor = _make_sensor(TrueNASAlertSensor, {})
    await sensor.restore(uuid="u2")
    sensor.coordinator.api.query.assert_awaited_once_with("alert.restore", ["u2"])
    sensor.coordinator.async_refresh.assert_awaited_once()


# ---------------------------
#   TrueNASRsyncSensor / TrueNASReplicationSensor / TrueNASSnapshotTaskSensor
# ---------------------------
async def test_rsync_start_skips_when_running() -> None:
    sensor = _make_sensor(TrueNASRsyncSensor, {"state": "RUNNING", "id": 1})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_not_awaited()


async def test_rsync_start_runs_task() -> None:
    sensor = _make_sensor(TrueNASRsyncSensor, {"state": "FINISHED", "id": 1})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_awaited_once_with(
        "rsynctask.run", 1, "rsynctask"
    )


async def test_replication_start_skips_when_waiting() -> None:
    sensor = _make_sensor(TrueNASReplicationSensor, {"state": "WAITING", "id": 2})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_not_awaited()


async def test_replication_start_runs_task() -> None:
    sensor = _make_sensor(TrueNASReplicationSensor, {"state": "FINISHED", "id": 2})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_awaited_once_with(
        "replication.run", 2, "replication"
    )


async def test_snapshottask_start_skips_when_running() -> None:
    sensor = _make_sensor(TrueNASSnapshotTaskSensor, {"state": "RUNNING", "id": 3})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_not_awaited()


async def test_snapshottask_start_runs_task() -> None:
    sensor = _make_sensor(TrueNASSnapshotTaskSensor, {"state": "FINISHED", "id": 3})
    await sensor.start()
    sensor.coordinator.async_run_task.assert_awaited_once_with(
        "pool.snapshottask.run", 3, "snapshottask"
    )


_SNAPSHOTTASK_DESC = TrueNASSensorEntityDescription(
    key="snapshottask",
    name="",
    data_path="snapshottask",
    data_attribute="state",
    data_name="dataset",
)


@pytest.mark.parametrize(
    ("naming_schema", "expected_name"),
    [
        ("auto-%Y-%m-%d_%H-%M_daily", "tank/data daily"),
        ("auto-%Y-%m-%d_%H-%M-weekly", "tank/data weekly"),
        ("auto-%Y-%m-%d_%H-%M", "tank/data"),
        ("unknown", "tank/data"),
    ],
)
def test_snapshottask_name_uses_naming_schema_suffix(
    naming_schema: str, expected_name: str
) -> None:
    sensor = _make_sensor(
        TrueNASSnapshotTaskSensor,
        {"id": 3, "dataset": "tank/data", "naming_schema": naming_schema},
        path="snapshottask",
        desc=_SNAPSHOTTASK_DESC,
    )
    assert sensor.name == expected_name


@pytest.mark.parametrize(
    ("schedule", "expected_name"),
    [
        (
            {"minute": "0", "hour": "*", "dom": "*", "month": "*", "dow": "*"},
            "tank/data Hourly",
        ),
        (
            {"minute": "0", "hour": "0", "dom": "*", "month": "*", "dow": "*"},
            "tank/data Daily",
        ),
        (
            {"minute": "0", "hour": "0", "dom": "*", "month": "*", "dow": "1"},
            "tank/data Weekly",
        ),
        (
            {"minute": "0", "hour": "0", "dom": "1", "month": "*", "dow": "*"},
            "tank/data Monthly",
        ),
        (
            # Contrary to any known TrueNAS preset (both dom and dow pinned);
            # dom is checked first, so this resolves to Monthly.
            {"minute": "0", "hour": "0", "dom": "1", "month": "*", "dow": "1"},
            "tank/data Monthly",
        ),
        (
            # No known preset matches (custom "every 2 hours" schedule) ->
            # no suffix, plain dataset-only name.
            {"minute": "0", "hour": "*/2", "dom": "*", "month": "*", "dow": "*"},
            "tank/data",
        ),
        (
            # A weekday range isn't a single fixed value -> not treated as
            # a pinned dow, so no suffix.
            {"minute": "0", "hour": "0", "dom": "*", "month": "*", "dow": "1-5"},
            "tank/data",
        ),
        (
            # A day-of-month list isn't a single fixed value either.
            {"minute": "0", "hour": "0", "dom": "1,15", "month": "*", "dow": "*"},
            "tank/data",
        ),
        (
            # A pinned month never occurs in any of the four presets, so the
            # whole schedule is left unclassified even though dom is pinned.
            {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "*"},
            "tank/data",
        ),
        (
            # A step on `minute` ("every 5 minutes") isn't a single fixed
            # value either, even though hour/dom/dow/month otherwise look
            # like the Hourly preset -> no suffix.
            {"minute": "*/5", "hour": "*", "dom": "*", "month": "*", "dow": "*"},
            "tank/data",
        ),
        (
            # Plain ints are accepted as pinned values too, not just
            # digit-only strings.
            {"minute": 0, "hour": 0, "dom": "*", "month": "*", "dow": "*"},
            "tank/data Daily",
        ),
        (
            # A missing `hour` key (None) is treated as wildcard, same as
            # an explicit "*".
            {"minute": "0", "hour": None, "dom": "*", "month": "*", "dow": "*"},
            "tank/data Hourly",
        ),
        (
            # A fully wildcard schedule (minute included) means "every
            # minute", not hourly -- Hourly requires minute to be pinned to
            # the run time within the hour, so this stays unclassified.
            {"minute": "*", "hour": "*", "dom": "*", "month": "*", "dow": "*"},
            "tank/data",
        ),
        ({}, "tank/data"),
        ("not-a-dict", "tank/data"),
    ],
)
def test_snapshottask_name_falls_back_to_schedule(
    schedule: dict | str, expected_name: str
) -> None:
    sensor = _make_sensor(
        TrueNASSnapshotTaskSensor,
        {
            "id": 3,
            "dataset": "tank/data",
            "naming_schema": "auto-%Y-%m-%d_%H-%M",
            "schedule": schedule,
        },
        path="snapshottask",
        desc=_SNAPSHOTTASK_DESC,
    )
    assert sensor.name == expected_name


def test_snapshottask_name_naming_schema_suffix_wins_over_schedule() -> None:
    sensor = _make_sensor(
        TrueNASSnapshotTaskSensor,
        {
            "id": 3,
            "dataset": "tank/data",
            "naming_schema": "auto-%Y-%m-%d_%H-%M_daily",
            "schedule": {
                "minute": "0",
                "hour": "*",
                "dom": "*",
                "month": "*",
                "dow": "*",
            },
        },
        path="snapshottask",
        desc=_SNAPSHOTTASK_DESC,
    )
    assert sensor.name == "tank/data daily"


# ---------------------------
#   TrueNASCloudsyncSensor
# ---------------------------
def _make_cloudsync(data: dict | None = None) -> TrueNASCloudsyncSensor:
    return _make_sensor(
        TrueNASCloudsyncSensor,
        {"id": 9, "description": "backup", **(data or {})},
        path="cloudsync",
    )


async def test_cloudsync_start_invalid_job_logs_and_returns() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.return_value = []
    await sensor.start()
    sensor.coordinator.async_run_task.assert_not_awaited()


async def test_cloudsync_start_already_running_skips() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.return_value = [{"job": {"state": "RUNNING"}}]
    await sensor.start()
    sensor.coordinator.async_run_task.assert_not_awaited()


async def test_cloudsync_start_success() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.return_value = [{"job": {"state": "FINISHED"}}]
    await sensor.start()
    sensor.coordinator.async_run_task.assert_awaited_once_with(
        "cloudsync.sync", 9, "cloudsync"
    )


async def test_cloudsync_stop_invalid_job_returns() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.return_value = []
    await sensor.stop()
    sensor.coordinator.api.query.assert_awaited_once()


async def test_cloudsync_stop_not_running_returns() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.return_value = [{"job": {"state": "FINISHED"}}]
    await sensor.stop()
    sensor.coordinator.api.query.assert_awaited_once()


async def test_cloudsync_stop_success() -> None:
    sensor = _make_cloudsync()
    sensor.coordinator.api.query.side_effect = [[{"job": {"state": "RUNNING"}}], None]
    await sensor.stop()
    sensor.coordinator.api.query.assert_awaited_with("cloudsync.abort", [9])


# ---------------------------
#   TrueNASDatasetSensor
# ---------------------------
def _make_dataset(data: dict | None = None) -> TrueNASDatasetSensor:
    return _make_sensor(
        TrueNASDatasetSensor,
        {"id": "tank/data", "name": "tank/data", **(data or {})},
        path="dataset",
    )


async def test_dataset_snapshot_success_uses_pool_snapshot() -> None:
    sensor = _make_dataset()
    sensor.coordinator.api.query.return_value = {"id": 1}
    await sensor.snapshot()
    sensor.coordinator.api.query.assert_awaited_once()
    assert sensor.coordinator.api.query.call_args.args[0] == "pool.snapshot.create"


async def test_dataset_snapshot_falls_back_to_zfs_snapshot() -> None:
    sensor = _make_dataset()
    sensor.coordinator.api.query.side_effect = [None, {"id": 1}]
    await sensor.snapshot()
    assert sensor.coordinator.api.query.await_count == 2
    assert sensor.coordinator.api.query.call_args.args[0] == "zfs.snapshot.create"


async def test_dataset_snapshot_both_fail_raises() -> None:
    sensor = _make_dataset()
    sensor.coordinator.api.query.side_effect = [None, None]
    sensor.coordinator.api.error = "no permission"
    with pytest.raises(HomeAssistantError) as exc_info:
        await sensor.snapshot()
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "snapshot",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "no permission",
    }


async def test_dataset_lock_rejects_unencrypted() -> None:
    sensor = _make_dataset({"encrypted": False})
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.lock()
    assert exc_info.value.translation_key == "dataset_not_encrypted"
    assert exc_info.value.translation_placeholders == {
        "dataset": "tank/data",
        "action": "lock",
    }


async def test_dataset_lock_already_locked_returns_early() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    await sensor.lock()
    sensor.coordinator.async_refresh.assert_awaited_once()
    sensor.coordinator.api.query.assert_not_awaited()


async def test_dataset_lock_runs_job_to_success() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": False})
    sensor.coordinator.api.query.side_effect = [
        42,
        {"state": "SUCCESS", "result": None},
    ]
    await sensor.lock(force_umount=True)
    assert sensor.coordinator.async_refresh.await_count == 2


async def test_dataset_unlock_rejects_unencrypted() -> None:
    sensor = _make_dataset({"encrypted": False})
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.unlock(passphrase="secret")
    assert exc_info.value.translation_key == "dataset_not_encrypted"
    assert exc_info.value.translation_placeholders == {
        "dataset": "tank/data",
        "action": "unlock",
    }


async def test_dataset_unlock_no_passphrase_raises() -> None:
    sensor = _make_dataset({"encrypted": True})
    sensor.coordinator.config_entry.data.pop("dataset_passphrases", None)
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.unlock()
    assert exc_info.value.translation_key == "missing_passphrase"
    assert exc_info.value.translation_placeholders == {"dataset": "tank/data"}


async def test_dataset_unlock_already_unlocked_returns_early() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": False})
    await sensor.unlock(passphrase="secret")
    sensor.coordinator.async_refresh.assert_awaited_once()
    sensor.coordinator.api.query.assert_not_awaited()


async def test_dataset_unlock_uses_stored_passphrase() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.config_entry.data["dataset_passphrases"] = {
        "tank/data": "stored-secret"
    }
    sensor.coordinator.api.query.side_effect = [42, {"state": "SUCCESS", "result": {}}]
    await sensor.unlock()
    job_call = sensor.coordinator.api.query.call_args_list[0]
    assert job_call.args[1][1]["datasets"][0]["passphrase"] == "stored-secret"


async def test_dataset_unlock_job_success_with_failed_entries_raises() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.api.query.side_effect = [
        42,
        {
            "state": "SUCCESS",
            "result": {"failed": {"tank/data": {"error": "bad passphrase"}}},
        },
    ]
    with pytest.raises(HomeAssistantError) as exc_info:
        await sensor.unlock(passphrase="wrong")
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "unlock",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "tank/data: bad passphrase",
    }


async def test_dataset_unlock_job_failed_state_raises() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.api.query.side_effect = [
        42,
        {"state": "FAILED", "error": "disk error"},
    ]
    with pytest.raises(HomeAssistantError) as exc_info:
        await sensor.unlock(passphrase="secret")
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "unlock",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "disk error",
    }


async def test_dataset_run_job_invalid_job_id_raises() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.api.query.return_value = None
    with pytest.raises(HomeAssistantError) as exc_info:
        await sensor.unlock(passphrase="secret")
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "unlock",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "invalid job id",
    }


async def test_dataset_wait_for_job_missing_job_exhausts_retries() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.api.query.side_effect = [42, None, None, None, None, None]
    with (
        patch(
            "homeassistant.components.truenas_ce.sensor.asyncio.sleep", new=AsyncMock()
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await sensor.unlock(passphrase="secret")
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "unlock",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "job 42 not found",
    }


async def test_dataset_wait_for_job_timeout_raises() -> None:
    sensor = _make_dataset({"encrypted": True, "locked": True})
    sensor.coordinator.api.query.side_effect = [42, {"state": "RUNNING"}]
    with (
        patch(
            "homeassistant.components.truenas_ce.sensor.asyncio.sleep",
            new=AsyncMock(side_effect=TimeoutError),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await sensor.unlock(passphrase="secret")
    assert exc_info.value.translation_key == "dataset_action_failed"
    assert exc_info.value.translation_placeholders == {
        "action": "unlock",
        "dataset": "tank/data",
        "host": sensor.coordinator.host,
        "reason": "timed out waiting for completion",
    }
    assert isinstance(exc_info.value.__cause__, TimeoutError)


async def test_dataset_passphrase_set_stores_in_config_entry() -> None:
    sensor = _make_dataset()
    sensor.hass = sensor.coordinator.hass
    await sensor.passphrase_set("new-secret")
    sensor.coordinator.hass.config_entries.async_update_entry.assert_called_once()


async def test_dataset_passphrase_set_no_name_raises() -> None:
    sensor = _make_dataset({"name": None})
    sensor._data["name"] = None
    with pytest.raises(ServiceValidationError) as exc_info:
        await sensor.passphrase_set("secret")
    assert exc_info.value.translation_key == "unknown_dataset_name"


# ---------------------------
#   TrueNASAppStatsSensor
# ---------------------------
def _app_stats_desc(key: str = "app_stats_cpu") -> TrueNASSensorEntityDescription:
    return TrueNASSensorEntityDescription(
        key=key, name="CPU", data_path="app_stats", data_attribute="cpu"
    )


def test_app_stats_standard_native_value_and_name() -> None:
    coordinator = make_coordinator(
        data={"app_stats": {"plex": {"app_name": "Plex", "cpu": 12.5}}}
    )
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    assert sensor.native_value == 12.5
    assert sensor.name == "Plex CPU"
    assert sensor.unique_id == "truenas-app_stats_cpu-plex"
    assert sensor.available is True


def test_app_stats_name_without_literal_name_no_translations() -> None:
    """Descriptions that only set translation_key (no literal `name`) must not
    leak HA's UNDEFINED sentinel into the name when no translations are loaded --
    regression test for the fix in PR #66.
    """
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu",
        translation_key="app_stats_cpu",
        data_path="app_stats",
        data_attribute="cpu",
    )
    coordinator = make_coordinator(
        data={"app_stats": {"plex": {"app_name": "Plex", "cpu": 12.5}}}
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex")
    sensor.platform_data = None
    assert sensor.name == "Plex app_stats_cpu"


def test_app_stats_name_without_literal_name_translated() -> None:
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu",
        translation_key="app_stats_cpu",
        data_path="app_stats",
        data_attribute="cpu",
    )
    coordinator = make_coordinator(
        data={"app_stats": {"plex": {"app_name": "Plex", "cpu": 12.5}}}
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex")
    sensor.platform_data = SimpleNamespace(
        platform_name="truenas_ce",
        domain="sensor",
        platform_translations={
            "component.truenas_ce.entity.sensor.app_stats_cpu.name": "CPU"
        },
    )
    assert sensor.name == "Plex CPU"


def test_app_stats_native_value_none_when_no_data() -> None:
    coordinator = make_coordinator(data={"app_stats": {}})
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    assert sensor.native_value is None


def test_app_stats_native_value_none_when_no_data_attribute() -> None:
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu", name="CPU", data_path="app_stats"
    )
    coordinator = make_coordinator(data={"app_stats": {"plex": {"app_name": "Plex"}}})
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex")
    assert sensor.native_value is None


def test_app_stats_network_native_value_converts_bytes_to_kib() -> None:
    coordinator = make_coordinator(
        data={
            "app_stats": {
                "plex": {
                    "app_name": "Plex",
                    "networks": [{"interface_name": "eth0", "rx": 2048}],
                }
            }
        }
    )
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx",
        name="RX",
        data_path="app_stats",
        data_attribute="rx",
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    assert sensor.native_value == 2.0


def test_app_stats_network_native_value_invalid_conversion_returns_none() -> None:
    coordinator = make_coordinator(
        data={
            "app_stats": {
                "plex": {
                    "app_name": "Plex",
                    "networks": [{"interface_name": "eth0", "rx": "bad"}],
                }
            }
        }
    )
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx",
        name="RX",
        data_path="app_stats",
        data_attribute="rx",
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    assert sensor.native_value is None


def test_app_stats_network_name_resolved() -> None:
    coordinator = make_coordinator(
        data={
            "app_stats": {
                "plex": {"app_name": "Plex", "networks": [{"interface_name": "eth0"}]}
            }
        }
    )
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    assert sensor.name == "Plex eth0 RX"


def test_app_stats_network_name_unresolved_uses_base_uid() -> None:
    coordinator = make_coordinator(data={"app_stats": {}})
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    assert sensor.name == "plex RX"


def test_app_stats_network_name_malformed_uid_returns_none() -> None:
    coordinator = make_coordinator(data={"app_stats": {}})
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "malformed")
    assert sensor.name is None


def test_app_stats_extra_state_attributes_network() -> None:
    coordinator = make_coordinator(
        data={
            "app_stats": {
                "plex": {"app_name": "Plex", "networks": [{"interface_name": "eth0"}]}
            }
        }
    )
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    attrs = sensor.extra_state_attributes
    assert attrs["app_name"] == "Plex"
    assert attrs["interface_name"] == "eth0"


def test_app_stats_extra_state_attributes_no_data_returns_attribution_only() -> None:
    coordinator = make_coordinator(data={"app_stats": {}})
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    attrs = sensor.extra_state_attributes
    assert "app_name" not in attrs
