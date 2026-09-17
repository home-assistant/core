"""TrueNAS sensor platform."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from logging import getLogger
import re
from typing import Any, cast, override

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_DATA_UNIT, DEFAULT_DATA_UNIT, SIGNAL_UPDATE_SENSORS
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import (
    TrueNASEntity,
    async_add_entities,
    format_unique_id,
    resolve_entry_identity,
)
from .helper import GB_SCALED_UNITS, scaled_data_unit
from .sensor_types import (  # noqa: F401
    SENSOR_SERVICES,
    SENSOR_TYPES,
    TrueNASSensorEntityDescription,
)

_LOGGER = getLogger(__name__)

# app_stats descriptions for these keys are composite (one entity per app+interface)
# and stay purely data-driven -- never subject to the restore-on-restart fallback.
NETWORK_SENSOR_KEYS = ("app_stats_network_rx", "app_stats_network_tx")

# Updates are centralized in the coordinator; entity actions may run unlimited.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TrueNASConfigEntry,
    _async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for TrueNAS component."""
    coordinator: TrueNASCoordinator | None = get_truenas_coordinator(config_entry)
    if coordinator is None:
        return

    platform = ep.async_get_current_platform()

    @callback
    def _discover_app_stats_sensors(
        updated_coordinator: TrueNASCoordinator | None = None,
    ) -> None:
        # Ignore refreshes from other config entries, or duplicate-unique-id
        # errors result when multiple TrueNAS entries are configured (#33).
        if updated_coordinator is not None and updated_coordinator is not coordinator:
            _LOGGER.debug(
                "Ignoring app-stats refresh for %s (%s); this platform belongs to "
                "%s (%s)",
                updated_coordinator.name,
                updated_coordinator.config_entry.entry_id,
                coordinator.name,
                coordinator.config_entry.entry_id,
            )
            return
        _discover_app_stats(platform, coordinator, _async_add_entities)

    _discover_app_stats_sensors()
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_UPDATE_SENSORS, _discover_app_stats_sensors
        )
    )

    dispatcher = {
        "TrueNASSensor": TrueNASSensor,
        "TrueNASAlertSensor": TrueNASAlertSensor,
        "TrueNASUptimeSensor": TrueNASUptimeSensor,
        "TrueNASCloudsyncSensor": TrueNASCloudsyncSensor,
        "TrueNASDatasetSensor": TrueNASDatasetSensor,
        "TrueNASDiskSensor": TrueNASDiskSensor,
        "TrueNASRsyncSensor": TrueNASRsyncSensor,
        "TrueNASReplicationSensor": TrueNASReplicationSensor,
        "TrueNASSnapshotTaskSensor": TrueNASSnapshotTaskSensor,
    }
    await async_add_entities(hass, config_entry, dispatcher)


@callback
def _discover_app_stats(
    platform: Any,
    coord: TrueNASCoordinator,
    add_entities: AddEntitiesCallback,
) -> None:
    """Discover dynamic app stats sensors for the current coordinator state."""
    app_stats_data = coord.data.get("app_stats", {})
    if not isinstance(app_stats_data, dict):
        _LOGGER.warning(
            "TrueNAS app stats returned malformed data: %s",
            app_stats_data,
        )
        app_stats_data = {}
    app_stats_entities: list[TrueNASAppStatsSensor] = []

    loaded = {
        entity.unique_id
        for entity in platform.entities.values()
        if entity.unique_id is not None
    }

    identity = resolve_entry_identity(coord.config_entry)

    # Standard (non-network) sensors need only the app's name, which is
    # already known synchronously via get_known_app_names() -- so they're
    # created from that instead of from app_stats_data, closing the gap
    # where they'd otherwise not exist yet (see TrueNASAppStatsSensor's
    # restore-on-restart fallback). Network sensors are keyed by interface
    # name, only known from a previous app.stats payload, so they stay
    # purely data-driven.
    known_app_names = coord.get_known_app_names()
    for description in _app_stats_descriptions():
        if description.data_composite_references:
            for uid, app_data in app_stats_data.items():
                _maybe_discover_app_stats_sensor(
                    description,
                    uid,
                    app_data,
                    identity,
                    loaded,
                    app_stats_entities,
                    coord,
                )
        else:
            for uid in known_app_names:
                _discover_standard_sensor(
                    description, uid, identity, loaded, app_stats_entities, coord
                )

    if app_stats_entities:
        add_entities(app_stats_entities)


def _app_stats_descriptions() -> list[TrueNASSensorEntityDescription]:
    """Sensor descriptions that belong to the app_stats dynamic family."""
    return [d for d in SENSOR_TYPES if d.func == "TrueNASAppStatsSensor"]


def _maybe_discover_app_stats_sensor(
    description: TrueNASSensorEntityDescription,
    uid: str,
    app_data: dict[str, Any],
    identity: str,
    loaded: set[str],
    entities: list[TrueNASAppStatsSensor],
    coord: TrueNASCoordinator,
) -> None:
    """Append a new entity if it is not already loaded."""
    if not app_data:
        return

    if description.key in NETWORK_SENSOR_KEYS:
        _discover_network_sensors(
            description, uid, app_data, identity, loaded, entities, coord
        )
    else:
        _discover_standard_sensor(description, uid, identity, loaded, entities, coord)


# Composite UIDs for app network sensors use the format ``app_name::interface_name``.
_APP_STATS_NETWORK_UID_SEPARATOR = "::"


def _compose_app_network_uid(base_uid: str, interface_name: str) -> str:
    """Compose a unique identifier for an app network interface sensor."""
    return f"{base_uid}{_APP_STATS_NETWORK_UID_SEPARATOR}{interface_name}"


def _parse_app_network_uid(uid: str) -> tuple[str | None, str | None]:
    """Parse an app network interface UID into base UID and interface name.

    Returns (None, None) if the UID is malformed (missing separator, or an
    empty base UID/interface name).
    """
    base_uid, sep, iface = uid.rpartition(_APP_STATS_NETWORK_UID_SEPARATOR)
    return (base_uid, iface) if sep and base_uid and iface else (None, None)


def _resolve_app_network_data(uid: str, app_stats: Any) -> dict[str, Any] | None:
    """Resolve a composite app-network UID to its merged sensor data.

    ``app_stats`` is typed ``Any`` (not ``dict[str, Any]``) because it comes
    straight from ``coordinator.data.get("app_stats", {})``, which can be a
    malformed non-dict payload on a broken API response.
    """
    base_uid, interface_name = _parse_app_network_uid(uid)
    if base_uid is None or interface_name is None:
        return None
    if not isinstance(app_stats, dict):
        return None
    main_data = app_stats.get(base_uid)
    if not isinstance(main_data, dict) or not isinstance(
        main_data.get("networks"), list
    ):
        return None
    return next(
        (
            {**main_data, "interface_name": interface_name, **net}
            for net in main_data["networks"]
            if (isinstance(net, dict) and net.get("interface_name") == interface_name)
        ),
        None,
    )


def _discover_network_sensors(
    description: TrueNASSensorEntityDescription,
    uid: str,
    app_data: dict[str, Any],
    identity: str,
    loaded: set[str],
    entities: list[TrueNASAppStatsSensor],
    coord: TrueNASCoordinator,
) -> None:
    """Create network interface sensors for one app entry."""
    networks = app_data.get("networks", [])
    if not isinstance(networks, list):
        return
    for net in networks:
        if not isinstance(net, dict):
            continue
        interface_name = net.get("interface_name")
        if not interface_name:
            continue
        composed_uid = _compose_app_network_uid(uid, interface_name)
        unique_id = format_unique_id(identity, description.key, composed_uid)
        if unique_id in loaded:
            continue
        entities.append(TrueNASAppStatsSensor(coord, description, composed_uid))
        loaded.add(unique_id)


def _discover_standard_sensor(
    description: TrueNASSensorEntityDescription,
    uid: str,
    identity: str,
    loaded: set[str],
    entities: list[TrueNASAppStatsSensor],
    coord: TrueNASCoordinator,
) -> None:
    """Create a single standard app stats sensor if not already loaded."""
    unique_id = format_unique_id(identity, description.key, uid)
    if unique_id in loaded:
        return
    entities.append(TrueNASAppStatsSensor(coord, description, uid))
    loaded.add(unique_id)


class TrueNASSensor(TrueNASEntity, SensorEntity):
    """Define an TrueNAS sensor."""

    entity_description: TrueNASSensorEntityDescription

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description: TrueNASSensorEntityDescription,
        uid: str | None = None,
    ) -> None:
        """Set up the sensor and derive its GB/GiB display unit preference."""
        super().__init__(coordinator, entity_description, uid)
        self._attr_suggested_unit_of_measurement = (
            self.entity_description.suggested_unit_of_measurement
        )

        if self._attr_suggested_unit_of_measurement in GB_SCALED_UNITS:
            data_unit = self.coordinator.config_entry.options.get(
                CONF_DATA_UNIT,
                self.coordinator.config_entry.data.get(
                    CONF_DATA_UNIT, DEFAULT_DATA_UNIT
                ),
            )
            value = (
                self._data.get(self.entity_description.data_attribute or "")
                if self._data
                else None
            )
            unit, precision = scaled_data_unit(value, data_unit == "GiB")
            self._attr_suggested_unit_of_measurement = unit
            if precision is not None:
                self._attr_suggested_display_precision = precision

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor.

        Uses .get() so a missing key degrades to unknown instead of raising.
        """
        value: StateType | date | datetime | Decimal = self._data.get(
            self.entity_description.data_attribute or ""
        )
        return value

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    data_uom = self._data[uom]
                    if isinstance(data_uom, str):
                        return data_uom
                    _LOGGER.debug(
                        "Sensor %s: data-derived UOM %s is %r, expected str",
                        self.entity_description.key,
                        uom,
                        data_uom,
                    )
                    return None

            return self.entity_description.native_unit_of_measurement

        return None


_DISK_TYPE_ICONS = {
    "HDD": "mdi:harddisk",
    "SSD": "mdi:chip",
    "SED": "mdi:chip",
}


class TrueNASDiskSensor(TrueNASSensor):
    """Disk temperature sensor.

    force_update keeps the history graph from appearing frozen when stable.
    """

    _attr_force_update = True

    @property
    @override
    def icon(self) -> str:
        """Return an icon based on the disk type (HDD / SSD / NVMe).

        TrueNAS reports NVMe drives as type=SSD, so devname takes priority.
        """
        if (self._data.get("devname") or "").lower().startswith("nvme"):
            return "mdi:expansion-card-variant"
        disk_type = (self._data.get("type") or "").upper()
        return _DISK_TYPE_ICONS.get(disk_type, "mdi:harddisk")


class TrueNASUptimeSensor(TrueNASSensor):
    """Define an TrueNAS Uptime sensor."""

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        val = self._data.get(self.entity_description.data_attribute or "")
        if isinstance(val, (int, float)) and val > 0:
            return utc_from_timestamp(val)
        return None


class TrueNASAlertSensor(TrueNASSensor):
    """Define a TrueNAS Alert sensor.

    Dismiss/restore actions are part of the HACS-distributed edition; this
    Bronze-scope submission is read-only, so they're not included here.
    """


class TrueNASDatasetSensor(TrueNASSensor):
    """Define an TrueNAS Dataset sensor."""


class TrueNASRsyncSensor(TrueNASSensor):
    """Define a TrueNAS Rsync task sensor."""


class TrueNASReplicationSensor(TrueNASSensor):
    """Define a TrueNAS Replication task sensor."""


_SNAPSHOT_SCHEMA_TOKEN_RE = re.compile(r"%[A-Za-z]")

# Cadence labels guessed from TrueNAS's cron `schedule` field presets; only
# verified against an hourly example (issue #55). Fallback when
# naming_schema carries no literal suffix of its own.
_SCHEDULE_LABEL_HOURLY = "Hourly"
_SCHEDULE_LABEL_DAILY = "Daily"
_SCHEDULE_LABEL_WEEKLY = "Weekly"
_SCHEDULE_LABEL_MONTHLY = "Monthly"

_SCHEDULE_FIELDS = ("minute", "dom", "dow", "hour", "month")


def _is_pinned_schedule_field(value: Any) -> bool:
    """Return True if a cron schedule field is a single fixed number.

    Bools are excluded since `isinstance(True, int)` is True in Python.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, str) and value.isdigit()


def _is_wildcard_schedule_field(value: Any) -> bool:
    """Return True if a cron schedule field is unset ("*" or absent)."""
    return value in ("*", None)


class TrueNASSnapshotTaskSensor(TrueNASSensor):
    """Define a TrueNAS periodic snapshot task sensor."""

    @property
    @override
    def name(self) -> str | None:
        """Disambiguate same-dataset tasks via naming_schema or schedule.

        Multiple tasks on one dataset otherwise collide, and HA appends a
        non-deterministic _2/_3 to the generated entity id (issue #55).
        """
        base_name = super().name
        suffix = self._naming_schema_suffix() or self._schedule_suffix()
        return f"{base_name} {suffix}" if base_name and suffix else base_name

    def _naming_schema_suffix(self) -> str | None:
        """Return the literal text trailing naming_schema's last %-token."""
        schema = self._data.get("naming_schema") if self._data else None
        if not isinstance(schema, str):
            return None
        matches = list(_SNAPSHOT_SCHEMA_TOKEN_RE.finditer(schema))
        if not matches:
            return None
        return schema[matches[-1].end() :].strip("-_ ") or None

    def _schedule_suffix(self) -> str | None:
        """Return a best-effort Hourly/Daily/Weekly/Monthly label, or None.

        TrueNAS's presets each pin exactly one of dom/dow/hour (plus
        minute); Hourly pins only minute. Anything else -- a step/range/list
        value, a pinned month, all wildcards, or dom+dow both pinned (cron
        OR-semantics, not "Monthly") -- falls outside every known preset and
        is left unclassified rather than guessed at.
        """
        schedule = self._data.get("schedule") if self._data else None
        if not isinstance(schedule, dict) or not schedule:
            return None
        minute, dom, dow, hour, month = (
            schedule.get(field) for field in _SCHEDULE_FIELDS
        )
        fields = (minute, dom, dow, hour, month)
        if any(
            not (_is_pinned_schedule_field(f) or _is_wildcard_schedule_field(f))
            for f in fields
        ):
            return None
        if _is_pinned_schedule_field(month):
            return None
        dom_pinned = _is_pinned_schedule_field(dom)
        dow_pinned = _is_pinned_schedule_field(dow)
        if dom_pinned and dow_pinned:
            return None
        if dom_pinned:
            return _SCHEDULE_LABEL_MONTHLY
        if dow_pinned:
            return _SCHEDULE_LABEL_WEEKLY
        if _is_pinned_schedule_field(hour):
            return _SCHEDULE_LABEL_DAILY
        # The `any(...)` guard above guarantees every field is pinned or
        # wildcard, and hour didn't match the pinned branch above, so hour
        # is wildcard here -- no need to re-check it. Hourly still requires
        # `minute` to be pinned; see the docstring note on fully wildcard
        # schedules above.
        if _is_pinned_schedule_field(minute):
            return _SCHEDULE_LABEL_HOURLY
        return None


class TrueNASCloudsyncSensor(TrueNASSensor):
    """Define an TrueNAS Cloudsync sensor."""


class TrueNASAppStatsSensor(TrueNASEntity, RestoreSensor):
    """Define a TrueNAS App Statistics sensor."""

    entity_description: TrueNASSensorEntityDescription

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description: TrueNASSensorEntityDescription,
        uid: str | None = None,
    ) -> None:
        """Initialize the app stats sensor."""
        # Set before super().__init__() -- it calls _refresh_data(), which
        # touches this attribute -- so the instance always has it, even on
        # the very first refresh done during construction.
        self._restored_native_value: StateType | date | datetime | Decimal | None = None
        self._awaiting_first_app_stats_event = False
        super().__init__(coordinator, entity_description, uid)

    @override
    async def async_added_to_hass(self) -> None:
        """Seed a restored value for the startup gap before the first app.stats push.

        Fetched before super().async_added_to_hass() so the restored value
        is already in place for that call's first state write; see
        ``_seed_restored_value_if_needed`` for why this gap exists at all.
        """
        await self._seed_restored_value_if_needed()
        await super().async_added_to_hass()

    async def _seed_restored_value_if_needed(self) -> None:
        """Stage a restored value to show until the first real app.stats event.

        TrueNAS's app.stats event source needs a full poll interval after
        (re)subscribing before it can send its first event at all (a CPU%
        reading requires two time-separated samples) -- see coordinator.py's
        ``start_app_stats``. Every HA/integration restart re-subscribes, so
        without this these sensors would show "unavailable" for a full
        interval (default 60s) after every restart. Cleared again by
        _refresh_data() the moment real data arrives, so a genuinely removed
        app still goes unavailable normally afterwards -- and left alone
        (returns early) if real data is already present, so a fast restart
        never overwrites live data with a stale restored one. Network (rx/tx)
        sensors are intentionally excluded via ``NETWORK_SENSOR_KEYS`` -- they
        stay purely data-driven, see _refresh_network_data() below.
        """
        if self._data or self.entity_description.key in NETWORK_SENSOR_KEYS:
            return
        restored = await self.async_get_last_sensor_data()
        if restored is not None and restored.native_value is not None:
            self._restored_native_value = restored.native_value
            self._awaiting_first_app_stats_event = True

    def _refresh_network_data(self) -> str | None:
        """Resolve composite network (rx/tx) sensor data; return the base app name."""
        base_uid, interface_name = _parse_app_network_uid(self._uid or "")
        resolved = None
        if base_uid is not None and interface_name is not None:
            resolved = _resolve_app_network_data(
                self._uid or "", self.coordinator.data.get("app_stats", {})
            )
        self._data = resolved or {}
        if not resolved:
            _LOGGER.debug(
                "Network sensor %s (%s) could not resolve interface data",
                self.entity_description.key,
                self._uid,
            )
        return base_uid

    def _refresh_standard_data(self) -> None:
        """Resolve a standard (per-app) sensor's data from app_stats."""
        app_stats = self.coordinator.data.get("app_stats")
        if isinstance(app_stats, dict):
            self._data = app_stats.get(self._uid, {})
        else:
            self._data = {}
            _LOGGER.debug(
                "App stats sensor %s: coordinator app_stats is %r, expected dict",
                self._uid,
                app_stats,
            )

    @override
    def _refresh_data(self) -> None:
        """Refresh cached data specifically from the app_stats directory structure."""
        if self.entity_description.key in NETWORK_SENSOR_KEYS:
            app_name = self._refresh_network_data()
        else:
            app_name = self._uid
            self._refresh_standard_data()

        # Clear the restored-placeholder flag once real data arrives, or once an
        # eagerly-created standard sensor's app is confirmed gone (see
        # get_known_app_names()) -- otherwise a removed app would show a frozen
        # stale value forever instead of going unavailable like any other
        # deleted app.
        if self._data or (
            self._awaiting_first_app_stats_event
            and app_name not in self.coordinator.get_known_app_names()
        ):
            self._awaiting_first_app_stats_event = False

    @override
    def _data_missing_is_available(self) -> bool:
        """Stay available on a restored value until the first real event lands."""
        return self._awaiting_first_app_stats_event

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available

    @property
    @override
    def unique_id(self) -> str:
        """Return a truly unique id, preventing conflict between apps sharing eth0."""
        return format_unique_id(self._identity, self.entity_description.key, self._uid)

    @property
    @override
    def name(self) -> str | None:
        """Return the dynamic friendly name for the entity."""
        desc_name = self._translated_description_name() or self.entity_description.key
        if self.entity_description.key in NETWORK_SENSOR_KEYS:
            base_uid, interface_name = _parse_app_network_uid(self._uid or "")
            if base_uid is not None and interface_name is not None:
                if resolved := _resolve_app_network_data(
                    self._uid or "", self.coordinator.data.get("app_stats", {})
                ):
                    return (
                        f"{resolved.get('app_name', self._uid)} "
                        f"{resolved.get('interface_name')} "
                        f"{desc_name}"
                    )
                return f"{base_uid} {desc_name}"
            return None

        app_name = self._data.get("app_name", self._uid)
        return f"{app_name} {desc_name}"

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the state of the sensor."""
        if not self._data:
            if self._awaiting_first_app_stats_event:
                return self._restored_native_value
            return None

        description = self.entity_description
        data_attribute = description.data_attribute
        if data_attribute is None:
            return None

        val = self._data.get(data_attribute)
        if val is None:
            return None

        if description.key in NETWORK_SENSOR_KEYS:
            try:
                # Backend provides bytes/sec; convert to KiB/s.
                return float(val) / 1024.0
            except (ValueError, TypeError):  # fmt: skip
                return None

        return cast("StateType | date | datetime | Decimal", val)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return extra state attributes for advanced card telemetry."""
        attrs = dict(super().extra_state_attributes or {})
        if not self._data:
            return attrs

        app_name = self._data.get("app_name")
        if app_name is not None:
            attrs["app_name"] = app_name
            if "interface_name" in self._data:
                interface_name = self._data.get("interface_name")
                if interface_name is not None:
                    attrs["interface_name"] = interface_name

        return attrs
