"""TrueNAS sensor platform."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from logging import getLogger
import re
from typing import Any, cast, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_DATA_UNIT, DEFAULT_DATA_UNIT, DOMAIN, SIGNAL_UPDATE_SENSORS
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import TrueNASEntity, async_add_entities, format_unique_id
from .helper import alert_action, scaled_data_unit
from .sensor_types import (  # noqa: F401
    SENSOR_SERVICES,
    SENSOR_TYPES,
    TrueNASSensorEntityDescription,
)

_LOGGER = getLogger(__name__)

# Updates are centralized in the coordinator; entity actions may run unlimited.
PARALLEL_UPDATES = 0


# ---------------------------
#   async_setup_entry
# ---------------------------
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
        _discover_app_stats(
            platform, updated_coordinator or coordinator, _async_add_entities
        )

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
        "TrueNASCertExpirySensor": TrueNASCertExpirySensor,
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
    """Discover dynamic app stats sensors for the current coordinator state.

    coord.data["app_stats"] is a dict keyed by app name. Each app-stats
    description may yield:
      - one standard sensor per app (e.g. cpu, memory), keyed by app_name
      - one sensor per network interface, keyed by the composite UID
        ``app_name::interface_name`` so apps sharing an NIC name remain unique
    """
    app_stats_data = coord.data.get("app_stats", {})
    app_stats_entities: list[TrueNASAppStatsSensor] = []

    loaded = {
        entity.unique_id
        for entity in platform.entities.values()
        if entity.unique_id is not None
    }

    inst = coord.config_entry.data[CONF_NAME]

    for description in _app_stats_descriptions():
        for uid, app_data in app_stats_data.items():
            _maybe_discover_app_stats_sensor(
                description, uid, app_data, inst, loaded, app_stats_entities, coord
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
    inst: str,
    loaded: set[str],
    entities: list[TrueNASAppStatsSensor],
    coord: TrueNASCoordinator,
) -> None:
    """Append a new entity if it is not already loaded.

    Network descriptions branch to ``_discover_network_sensors`` (one composite
    UID per interface). All other descriptions branch to ``_discover_standard_sensor``
    (one entity per app).
    """
    if not app_data:
        return

    if description.key in (
        "app_stats_network_rx",
        "app_stats_network_tx",
    ):
        _discover_network_sensors(
            description, uid, app_data, inst, loaded, entities, coord
        )
    else:
        _discover_standard_sensor(description, uid, inst, loaded, entities, coord)


# ---------------------------
#   App Stats Network UID Helpers
# ---------------------------
# Composite UIDs for app network sensors use the format ``app_name::interface_name``.
# These helpers centralize composition, parsing, and data resolution so discovery,
# entity refresh, and naming all stay consistent.
_APP_STATS_NETWORK_UID_SEPARATOR = "::"


def _compose_app_network_uid(base_uid: str, interface_name: str) -> str:
    """Compose a unique identifier for an app network interface sensor.

    Network sensors share the same ``app_name`` base UID as other app-stats
    sensors; the ``interface_name`` suffix differentiates per-NIC readings.
    This helper is the canonical way to build composite UIDs so the delimiter
    and formatting stay consistent across discovery and entity construction.
    """
    return f"{base_uid}{_APP_STATS_NETWORK_UID_SEPARATOR}{interface_name}"


def _parse_app_network_uid(uid: str) -> tuple[str | None, str | None]:
    """Parse an app network interface UID into base UID and interface name.

    Uses ``_APP_STATS_NETWORK_UID_SEPARATOR`` to split the UID. Returns:
        A tuple of (base_uid, interface_name). If the UID does not contain
        the expected separator, (None, None) is returned to signal a parse
        failure. Callers should treat a None base_uid as an unknown/malformed
        network sensor and skip/reset the entity.

        Any UID where either the base UID or interface name is empty after
        splitting is also treated as malformed and returns (None, None).
    """
    base_uid, sep, iface = uid.rpartition(_APP_STATS_NETWORK_UID_SEPARATOR)
    return (base_uid, iface) if sep and base_uid and iface else (None, None)


def _resolve_app_network_data(
    uid: str, app_stats: dict[str, Any]
) -> dict[str, Any] | None:
    """Resolve a composite app-network UID to its merged sensor data.

    Uses ``_APP_STATS_NETWORK_UID_SEPARATOR`` to split the UID, then looks up
    the base app in ``app_stats`` and merges the matching network interface
    payload. Pure helper that operates on the ``app_stats`` payload directly
    so it can be tested without a full coordinator. Returns the app_stats
    entry merged with the matching network interface payload, or ``None`` if
    the UID is malformed or the interface is unknown.
    """
    base_uid, interface_name = _parse_app_network_uid(uid)
    if base_uid is None or interface_name is None:
        return None
    main_data = app_stats.get(base_uid, {})
    if not main_data or not isinstance(main_data.get("networks"), list):
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
    inst: str,
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
        unique_id = format_unique_id(inst, description.key, composed_uid)
        if unique_id in loaded:
            continue
        entities.append(TrueNASAppStatsSensor(coord, description, composed_uid))
        loaded.add(unique_id)


def _discover_standard_sensor(
    description: TrueNASSensorEntityDescription,
    uid: str,
    inst: str,
    loaded: set[str],
    entities: list[TrueNASAppStatsSensor],
    coord: TrueNASCoordinator,
) -> None:
    """Create a single standard app stats sensor if not already loaded."""
    unique_id = format_unique_id(inst, description.key, uid)
    if unique_id in loaded:
        return
    entities.append(TrueNASAppStatsSensor(coord, description, uid))
    loaded.add(unique_id)


# ---------------------------
#   TrueNASSensor
# ---------------------------
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

        if self._attr_suggested_unit_of_measurement in (
            UnitOfInformation.GIGABYTES,
            UnitOfInformation.GIBIBYTES,
        ):
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

        Uses .get() so a transient API failure that empties the coordinator data
        degrades the state to unknown instead of raising a KeyError mid-update.
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
                    data_uom: str | None = self._data[uom]
                    return data_uom

            return self.entity_description.native_unit_of_measurement

        return None


# ---------------------------
#   TrueNASCertExpirySensor
# ---------------------------
_DAYS_PER_YEAR = 365.25


class TrueNASCertExpirySensor(TrueNASSensor):
    """Certificate expiry sensor with adaptive unit (years ≥ 365 d, else days)."""

    @property
    @override
    def native_value(self) -> StateType:
        """Return days or fractional years depending on magnitude."""
        days: float | None = self._data.get(
            self.entity_description.data_attribute or ""
        )
        if days is None:
            return None
        return round(days / _DAYS_PER_YEAR, 1) if days >= 365 else days

    @property
    @override
    def native_unit_of_measurement(self) -> UnitOfTime:
        """Switch unit between days and years based on the raw value."""
        days: float | None = self._data.get(
            self.entity_description.data_attribute or ""
        )
        if days is not None and days >= 365:
            return UnitOfTime.YEARS
        return UnitOfTime.DAYS


# ---------------------------
#   TrueNASDiskSensor
# ---------------------------
_DISK_TYPE_ICONS = {
    "HDD": "mdi:harddisk",
    "SSD": "mdi:chip",
    "SED": "mdi:chip",
}


class TrueNASDiskSensor(TrueNASSensor):
    """Disk temperature sensor.

    force_update ensures HA records every poll value even when the temperature
    is stable, so the history graph never appears frozen.
    """

    _attr_force_update = True

    @property
    @override
    def icon(self) -> str:
        """Return an icon based on the disk type (HDD / SSD / NVMe).

        TrueNAS reports NVMe drives as type=SSD, so devname prefix takes
        priority over the type field.
        """
        if (self._data.get("devname") or "").lower().startswith("nvme"):
            return "mdi:expansion-card-variant"
        disk_type = (self._data.get("type") or "").upper()
        return _DISK_TYPE_ICONS.get(disk_type, "mdi:harddisk")


# ---------------------------
#   TrueNASUptimeSensor
# ---------------------------
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


# ---------------------------
#   TrueNASAlertSensor
# ---------------------------
class TrueNASAlertSensor(TrueNASSensor):
    """Define a TrueNAS Alert sensor with dismiss/restore actions."""

    async def dismiss(self, **kwargs: Any) -> None:
        """Dismiss a TrueNAS alert by its UUID."""
        if uuid := kwargs.get("uuid"):
            await alert_action(self.coordinator, uuid, "dismiss")
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="missing_uuid"
            )

    async def restore(self, **kwargs: Any) -> None:
        """Restore (un-dismiss) a previously dismissed TrueNAS alert by UUID."""
        if uuid := kwargs.get("uuid"):
            await alert_action(self.coordinator, uuid, "restore")
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="missing_uuid"
            )


# ---------------------------
#   TrueNASDatasetSensor
# ---------------------------
class TrueNASDatasetSensor(TrueNASSensor):
    """Define an TrueNAS Dataset sensor."""


# ---------------------------
#   TrueNASRsyncSensor
# ---------------------------
class TrueNASRsyncSensor(TrueNASSensor):
    """Define a TrueNAS Rsync task sensor."""


# ---------------------------
#   TrueNASReplicationSensor
# ---------------------------
class TrueNASReplicationSensor(TrueNASSensor):
    """Define a TrueNAS Replication task sensor."""


# ---------------------------
#   TrueNASSnapshotTaskSensor
# ---------------------------
_SNAPSHOT_SCHEMA_TOKEN_RE = re.compile(r"%[A-Za-z]")

# Best-effort cadence labels guessed from TrueNAS's cron `schedule` field,
# matching its known periodic-snapshot-task presets (dom set -> monthly, dow
# set -> weekly, hour set -> daily, else hourly). This is unverified against
# real daily/weekly/monthly schedules (issue #55) -- HA debug logs of
# pool.snapshottask.query were truncated when this was written, so only an
# hourly example was available. Only used as a fallback when naming_schema
# carries no literal suffix of its own.
_SCHEDULE_LABEL_HOURLY = "Hourly"
_SCHEDULE_LABEL_DAILY = "Daily"
_SCHEDULE_LABEL_WEEKLY = "Weekly"
_SCHEDULE_LABEL_MONTHLY = "Monthly"

# The cron fields read off a snapshot task's `schedule` dict, centralised
# here so the field names are typed once rather than repeated at each call
# site that inspects the dict.
_SCHEDULE_FIELDS = ("minute", "dom", "dow", "hour", "month")


def _is_pinned_schedule_field(value: Any) -> bool:
    """Return True if a cron schedule field is a single fixed number.

    TrueNAS's simple Hourly/Daily/Weekly/Monthly presets only ever pin a
    field to one plain number. The API is expected to send these as
    digit-only strings, but plain ints are accepted too in case a future
    or unexpected response shape uses them (bools are excluded since
    `isinstance(True, int)` is True in Python).
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

        Several snapshot tasks (hourly/daily/weekly, ...) commonly share one
        dataset, so the dataset-only name collides and HA appends
        non-deterministic _2/_3 to the generated entity id (issue #55). When
        naming_schema carries literal text after its last strftime token
        (e.g. "auto-%Y-%m-%d_%H-%M_daily" -> "daily"), append it. Otherwise
        fall back to a cadence label guessed from the task's cron `schedule`
        (see _schedule_suffix). Tasks matching neither keep today's
        dataset-only name, so single-task-per-dataset setups aren't
        force-renamed.
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
        """Return a best-effort Hourly/Daily/Weekly/Monthly label.

        Derived from the task's cron `schedule` dict (minute/hour/dom/month/
        dow) using TrueNAS's known periodic-snapshot-task presets, which pin
        exactly one of dom/dow/hour to a single fixed number, pin `minute`
        to a single fixed number too (the run time within that hour/day),
        and leave `month` plus the remaining fields at "*". If any field is
        neither wildcarded nor a single fixed number -- a step ("*/2" on
        `minute` or `hour`), range ("1-5") or list ("1,15") -- or if `month`
        is pinned (which never occurs in any of the four presets), the
        schedule doesn't match a known preset at all, so it's left
        unclassified rather than guessed at from whichever field happens to
        still look pinned. `minute` itself never distinguishes between
        presets (every preset pins it), so it's only used for this shape
        check, not for the dom -> dow -> hour classification below, which
        means a schedule that (contrary to any known preset) has both dom
        and dow pinned is labeled Monthly. An empty `schedule` dict (no
        fields at all) is rejected up front rather than falling through to
        "every field is missing, so every field is wildcard" -> Hourly, and
        a fully wildcard schedule (minute included) is likewise left
        unclassified rather than labeled Hourly, since a genuine Hourly
        preset always pins `minute` to the run time within the hour --
        minute *also* being "*" would mean "every minute", not hourly.
        Tasks matching no preset keep the plain dataset-only name rather
        than risk a misleading guess.
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
        if _is_pinned_schedule_field(dom):
            return _SCHEDULE_LABEL_MONTHLY
        if _is_pinned_schedule_field(dow):
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


# ---------------------------
#   TrueNASCloudsyncSensor
# ---------------------------
class TrueNASCloudsyncSensor(TrueNASSensor):
    """Define an TrueNAS Cloudsync sensor."""


# ---------------------------
#   TrueNASAppStatsSensor
# ---------------------------
class TrueNASAppStatsSensor(TrueNASEntity, SensorEntity):
    """Define a TrueNAS App Statistics sensor."""

    entity_description: TrueNASSensorEntityDescription

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description: TrueNASSensorEntityDescription,
        uid: str | None = None,
    ) -> None:
        """Initialize the app stats sensor."""
        super().__init__(coordinator, entity_description, uid)

    @override
    def _refresh_data(self) -> None:
        """Refresh cached data specifically from the app_stats directory structure."""
        if self.entity_description.key in (
            "app_stats_network_rx",
            "app_stats_network_tx",
        ):
            resolved = None
            base_uid, interface_name = _parse_app_network_uid(self._uid or "")
            if base_uid is not None and interface_name is not None:
                resolved = _resolve_app_network_data(
                    self._uid or "", self.coordinator.data.get("app_stats", {})
                )
                self._data = resolved or {}
            else:
                self._data = {}
            self._has_valid_interface_payload = bool(resolved)
            if not resolved:
                _LOGGER.debug(
                    "Network sensor %s (%s) could not resolve interface data",
                    self.entity_description.key,
                    self._uid,
                )
        else:
            self._data = self.coordinator.data.get("app_stats", {}).get(self._uid, {})

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available

    @property
    @override
    def unique_id(self) -> str:
        """Return a truly unique id, preventing conflict between apps sharing eth0."""
        return format_unique_id(self._inst, self.entity_description.key, self._uid)

    @property
    @override
    def name(self) -> str | None:
        """Return the dynamic friendly name for the entity."""
        desc_name = self._translated_description_name() or self.entity_description.key
        if self.entity_description.key in (
            "app_stats_network_rx",
            "app_stats_network_tx",
        ):
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
            return None

        description = self.entity_description
        data_attribute = description.data_attribute
        if data_attribute is None:
            return None

        val = self._data.get(data_attribute)
        if val is None:
            return None

        if description.key in (
            "app_stats_network_rx",
            "app_stats_network_tx",
        ):
            try:
                # Backend provides bytes/sec; convert to KiB/s to match
                # the declared unit.
                return float(val) / 1024.0
            except (ValueError, TypeError):  # fmt: skip
                # Parsing failed; avoid returning a value with incorrect units.
                # Returning None keeps the state consistent with the declared unit.
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
