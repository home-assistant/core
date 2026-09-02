"""Unit tests for sensor.py."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.truenas_ce import sensor as sensor_mod
from homeassistant.components.truenas_ce.const import CONF_DATA_UNIT
from homeassistant.components.truenas_ce.sensor import (
    TrueNASAppStatsSensor,
    TrueNASDiskSensor,
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
    """Composing then parsing an app/interface uid returns the original parts."""
    uid = _compose_app_network_uid("plex", "eth0")
    assert uid == "plex::eth0"
    assert _parse_app_network_uid(uid) == ("plex", "eth0")


@pytest.mark.parametrize("uid", ["no-separator", "::eth0", "plex::", "::"])
def test_parse_app_network_uid_malformed_returns_none_none(uid: str) -> None:
    """Uids missing a proper `base::interface` split parse to (None, None)."""
    assert _parse_app_network_uid(uid) == (None, None)


def test_resolve_app_network_data_malformed_uid_returns_none() -> None:
    """A malformed uid resolves to no network data."""
    assert _resolve_app_network_data("bad-uid", {}) is None


def test_resolve_app_network_data_unknown_base_returns_none() -> None:
    """A uid whose base app is not present in app_stats resolves to None."""
    assert _resolve_app_network_data("plex::eth0", {}) is None


def test_resolve_app_network_data_non_dict_app_stats_returns_none() -> None:
    """A malformed, non-dict app_stats payload resolves to None instead of raising."""
    assert _resolve_app_network_data("plex::eth0", "not-a-dict") is None


def test_resolve_app_network_data_networks_not_list_returns_none() -> None:
    """A non-list `networks` value resolves to None instead of raising."""
    app_stats = {"plex": {"networks": "not-a-list"}}
    assert _resolve_app_network_data("plex::eth0", app_stats) is None


def test_resolve_app_network_data_base_entry_not_dict_returns_none() -> None:
    """A non-dict base entry resolves to None instead of raising AttributeError."""
    app_stats = {"plex": "not-a-dict"}
    assert _resolve_app_network_data("plex::eth0", app_stats) is None


def test_resolve_app_network_data_no_matching_interface_returns_none() -> None:
    """No matching interface_name in the networks list resolves to None."""
    app_stats = {"plex": {"networks": [{"interface_name": "eth1"}]}}
    assert _resolve_app_network_data("plex::eth0", app_stats) is None


def test_resolve_app_network_data_returns_merged_payload() -> None:
    """A matching interface merges the app and interface fields into one dict."""
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
    """A non-list `networks` value produces no discovered entities."""
    entities: list = []
    _discover_network_sensors(
        _net_desc(), "plex", {"networks": "bad"}, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_discover_network_sensors_ignores_non_dict_and_missing_name() -> None:
    """Non-dict network entries and ones missing interface_name are skipped."""
    entities: list = []
    app_data = {"networks": ["not-a-dict", {}, {"interface_name": ""}]}
    _discover_network_sensors(
        _net_desc(), "plex", app_data, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_discover_network_sensors_creates_entity_and_skips_loaded() -> None:
    """A new interface creates one entity; a second pass skips the loaded one."""
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
    """A new app creates one entity; a second pass skips the already-loaded one."""
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
    """Empty app data produces no discovered entities."""
    entities: list = []
    _maybe_discover_app_stats_sensor(
        _net_desc(), "plex", {}, "inst", set(), entities, MagicMock()
    )
    assert not entities


def test_maybe_discover_app_stats_sensor_routes_network_key() -> None:
    """A network-keyed description routes to the composite app::interface uid."""
    entities: list = []
    coord = make_coordinator()
    app_data = {"networks": [{"interface_name": "eth0"}]}
    _maybe_discover_app_stats_sensor(
        _net_desc(), "plex", app_data, "inst", set(), entities, coord
    )
    assert len(entities) == 1
    assert entities[0]._uid == "plex::eth0"


def test_maybe_discover_app_stats_sensor_routes_standard_key() -> None:
    """A standard-keyed description routes to a plain app-name uid."""
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
    """New app-stats entities are discovered and passed to the add_entities callback."""
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
    """No app-stats data means the add_entities callback is never invoked."""
    coord = make_coordinator(data={"app_stats": {}})
    platform = SimpleNamespace(entities={})
    add_entities = MagicMock()
    _discover_app_stats(platform, coord, add_entities)
    add_entities.assert_not_called()


# ---------------------------
#   TrueNASSensor
# ---------------------------
def test_native_value_returns_data_attribute() -> None:
    """native_value returns the raw value of the configured data attribute."""
    sensor = _make_sensor(TrueNASSensor, {"value": 42})
    assert sensor.native_value == 42


def test_native_unit_of_measurement_plain() -> None:
    """A plain, non-`data_`-prefixed unit is returned unchanged."""
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
    """No configured unit yields native_unit_of_measurement of None."""
    sensor = _make_sensor(TrueNASSensor, {"value": 1})
    assert sensor.native_unit_of_measurement is None


def test_native_unit_of_measurement_data_prefixed_present() -> None:
    """A `data__field` unit resolves to that field's value when present."""
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
    """A `data__field` unit falls back to the raw spec string when field is absent."""
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
    """A GiB data-unit option keeps the suggested unit at GIBIBYTES."""
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
    """A GB data-unit entry falls back from entry.data, scaling the suggested unit."""
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
    """A non-data-size suggested unit (e.g. MB/s) is left untouched."""
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
    """The disk icon depends on device name (NVMe) and disk type."""
    sensor = _make_sensor(TrueNASDiskSensor, {"devname": devname, "type": disk_type})
    assert sensor.icon == expected


# ---------------------------
#   TrueNASUptimeSensor
# ---------------------------
def test_uptime_native_value_positive() -> None:
    """A positive uptime timestamp is returned as a datetime."""
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 1735689600})
    assert isinstance(sensor.native_value, datetime)


def test_uptime_native_value_zero_is_none() -> None:
    """An uptime value of zero yields native_value of None."""
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 0})
    assert sensor.native_value is None


# ---------------------------
#   TrueNASSnapshotTaskSensor
# ---------------------------
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
    """The entity name appends a period suffix parsed from the naming schema."""
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
            # Standard cron OR-semantics apply when dom and dow are both
            # pinned (runs on either match, not just monthly on the dom
            # days), so this isn't a real preset and stays unclassified.
            {"minute": "0", "hour": "0", "dom": "1", "month": "*", "dow": "1"},
            "tank/data",
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
    """When the naming schema has no known suffix, the cron schedule is classified."""
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
    """A recognized naming-schema suffix takes priority over schedule classification."""
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
#   TrueNASAppStatsSensor
# ---------------------------
def _app_stats_desc(key: str = "app_stats_cpu") -> TrueNASSensorEntityDescription:
    return TrueNASSensorEntityDescription(
        key=key, name="CPU", data_path="app_stats", data_attribute="cpu"
    )


def test_app_stats_standard_native_value_and_name() -> None:
    """A standard app-stats sensor exposes its value, app-prefixed name and id."""
    coordinator = make_coordinator(
        data={"app_stats": {"plex": {"app_name": "Plex", "cpu": 12.5}}}
    )
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    assert sensor.native_value == 12.5
    assert sensor.name == "Plex CPU"
    assert sensor.unique_id == "truenas-app_stats_cpu-plex"
    assert sensor.available is True


def test_app_stats_name_without_literal_name_no_translations() -> None:
    """Descriptions that only set translation_key (no literal `name`) must not.

    Leak HA's UNDEFINED sentinel into the name when no translations are loaded --
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
    """A translation_key-only description resolves to the loaded translation."""
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
    """No app_stats entry for the app yields native_value of None."""
    coordinator = make_coordinator(data={"app_stats": {}})
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    assert sensor.native_value is None


def test_app_stats_native_value_none_when_no_data_attribute() -> None:
    """No configured data_attribute yields native_value of None."""
    desc = TrueNASSensorEntityDescription(
        key="app_stats_cpu", name="CPU", data_path="app_stats"
    )
    coordinator = make_coordinator(data={"app_stats": {"plex": {"app_name": "Plex"}}})
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex")
    assert sensor.native_value is None


def test_app_stats_network_native_value_converts_bytes_to_kib() -> None:
    """A network sensor's byte value is converted to KiB."""
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
    """A non-numeric network byte value yields native_value of None."""
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
    """A resolvable network sensor's name includes app name and interface."""
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
    """An unresolvable network sensor falls back to the uid's base app name."""
    coordinator = make_coordinator(data={"app_stats": {}})
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "plex::eth0")
    assert sensor.name == "plex RX"


def test_app_stats_network_name_malformed_uid_returns_none() -> None:
    """A malformed uid yields a name of None."""
    coordinator = make_coordinator(data={"app_stats": {}})
    desc = TrueNASSensorEntityDescription(
        key="app_stats_network_rx", name="RX", data_path="app_stats"
    )
    sensor = TrueNASAppStatsSensor(coordinator, desc, "malformed")
    assert sensor.name is None


def test_app_stats_extra_state_attributes_network() -> None:
    """A network sensor's extra state attributes include app_name and interface_name."""
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
    """With no resolvable app data, extra state attributes omit app_name."""
    coordinator = make_coordinator(data={"app_stats": {}})
    sensor = TrueNASAppStatsSensor(coordinator, _app_stats_desc(), "plex")
    attrs = sensor.extra_state_attributes
    assert "app_name" not in attrs
