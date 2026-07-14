"""Bosch Smart Home Camera — Sensor Platform.

Creates sensor entities per camera:
  • {Name} Status              — ONLINE / OFFLINE / UNKNOWN
  • {Name} Last Event          — timestamp of the most recent motion event (device class: timestamp)
  • {Name} Events Today        — count of motion events today
  • {Name} WiFi Signal         — WiFi signal strength as percentage (device_class: signal_strength)
                                  attributes: ssid, ip_address, mac_address
  • {Name} Firmware Version    — firmware version string from /v11/video_inputs
                                  attributes: up_to_date
  • {Name} Ambient Light Level — ambient light sensor level (0.0–1.0) as percentage
                                  from GET /v11/video_inputs/{id}/ambient_light_sensor_level
  • {Name} LED Dimmer          — LED dimmer value 0–100% via RCP protocol (0x0c22)
                                  only for cameras with featureSupport.light = True
"""

import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .time_utils import parse_bosch_timestamp


def _event_is_today_local(ts_str: str | None) -> bool:
    """True if a Bosch event timestamp falls on today's *local* calendar date.

    Buckets by the local date of the event's true instant (offset honored),
    not by a naive string prefix — see time_utils / issue #34. A Bosch
    timestamp already carries the local offset, so its instant maps to the
    correct local day even across the UTC midnight boundary.
    """
    dt_utc = parse_bosch_timestamp(ts_str)
    if dt_utc is None:
        return False
    local_dt: datetime = dt_util.as_local(dt_utc)
    now_local: datetime = dt_util.now()
    return local_dt.date() == now_local.date()


from . import BoschCameraCoordinator, get_options
from .const import CONF_ENABLE_AI_DESCRIPTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = (
    0  # coordinator handles all updates; no per-entity parallelism needed
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each camera."""
    opts = get_options(config_entry)
    if not opts.get("enable_sensors", True):
        _LOGGER.debug("Sensors disabled in options — skipping sensor platform")
        return

    coordinator = config_entry.runtime_data

    entities = []
    for cam_id in coordinator.data:
        entities.extend(
            [
                BoschCameraStatusSensor(coordinator, cam_id, config_entry),
                BoschCameraLastEventSensor(coordinator, cam_id, config_entry),
                BoschCameraEventsTodaySensor(coordinator, cam_id, config_entry),
                BoschWifiSignalSensor(coordinator, cam_id, config_entry),
                BoschFirmwareVersionSensor(coordinator, cam_id, config_entry),
                BoschAmbientLightSensor(coordinator, cam_id, config_entry),
                BoschClockOffsetSensor(coordinator, cam_id, config_entry),
                BoschMotionSensitivitySensor(coordinator, cam_id, config_entry),
                BoschLastEventTypeSensor(coordinator, cam_id, config_entry),
                BoschMovementEventsTodaySensor(coordinator, cam_id, config_entry),
                BoschAudioEventsTodaySensor(coordinator, cam_id, config_entry),
                BoschUnreadEventsCountSensor(coordinator, cam_id, config_entry),
                BoschStreamStatusSensor(coordinator, cam_id, config_entry),
            ]
        )
        # LED Dimmer via RCP — only for cameras with a physical light (featureSupport.light)
        cam_info = coordinator.data[cam_id].get("info", {})
        has_light = cam_info.get("featureSupport", {}).get("light", False)
        if has_light:
            entities.append(BoschLedDimmerSensor(coordinator, cam_id, config_entry))
        # Commissioned status (diagnostic, disabled by default)
        entities.append(BoschCommissionedSensor(coordinator, cam_id, config_entry))
        # Cloud rules count (diagnostic, disabled by default)
        entities.append(BoschRulesCountSensor(coordinator, cam_id, config_entry))
        # Phase 2 RCP sensors (diagnostic, disabled by default)
        entities.append(BoschAlarmCatalogSensor(coordinator, cam_id, config_entry))
        entities.append(BoschMotionZonesSensor(coordinator, cam_id, config_entry))
        entities.append(BoschPrivateAreasSensor(coordinator, cam_id, config_entry))
        entities.append(BoschTlsCertSensor(coordinator, cam_id, config_entry))
        entities.append(BoschNetworkServicesSensor(coordinator, cam_id, config_entry))
        entities.append(BoschIvaCatalogSensor(coordinator, cam_id, config_entry))
        # Gen2-only sensors
        from .models import get_model_config as _gmc_setup

        hw_setup = cam_info.get("hardwareVersion", "")
        if _gmc_setup(hw_setup).generation >= 2:
            # Ambient-light schedule is Outdoor-only (Indoor II has no RGB lights)
            if hw_setup not in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
                entities.append(
                    BoschAmbientLightScheduleSensor(coordinator, cam_id, config_entry)
                )
        # Gen2 Indoor II — alarm state sensor
        if hw_setup in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
            entities.append(BoschAlarmStateSensor(coordinator, cam_id, config_entry))
        # F4: ONVIF scopes sensor (LAN, disabled by default)
        entities.append(BoschOnvifScopesSensor(coordinator, cam_id, config_entry))
        # F6: RCP protocol version sensor (LAN, disabled by default)
        entities.append(BoschRcpVersionSensor(coordinator, cam_id, config_entry))
    # Integration-level sensor: FCM push status (one per integration, not per camera)
    first_cam_id = next(iter(coordinator.data), None)
    if first_cam_id:
        entities.append(
            BoschFcmPushStatusSensor(coordinator, first_cam_id, config_entry)
        )
        # Bosch community-RSS-derived maintenance window (one per integration).
        # Stays available even when the cloud is unreachable — that is the
        # scenario it exists for.
        entities.append(
            BoschCloudMaintenanceSensor(coordinator, first_cam_id, config_entry)
        )
        # F13: Cloud feature-flags sensor (account-level, one per integration, disabled by default)
        entities.append(
            BoschCloudFeatureFlagsSensor(coordinator, first_cam_id, config_entry)
        )
    # Mini-NVR diagnostic sensor — surfaces drain-watcher state per camera so
    # users can answer "is recording reaching the target?". Disabled by
    # default; enable via the entity registry. One per camera.
    if opts.get("enable_nvr", False):
        for cam_id in coordinator.data:
            entities.append(BoschNvrStateSensor(coordinator, cam_id, config_entry))
    # AI Snapshot Description sensor — only when option is enabled
    if opts.get(CONF_ENABLE_AI_DESCRIPTION, False):
        for cam_id in coordinator.data:
            entities.append(
                BoschCameraAiDescriptionSensor(coordinator, cam_id, config_entry)
            )
    # External stream URL sensors (main + sub). Per-camera, always registered
    # so the BoschExternalStreamSwitch can toggle their value without dynamic
    # entity (re-)registration. Disabled in entity registry by default;
    # surfaced only when the user enables them for a specific camera.
    for cam_id in coordinator.data:
        entities.append(BoschStreamUrlSensor(coordinator, cam_id, config_entry))
        entities.append(BoschStreamUrlSubSensor(coordinator, cam_id, config_entry))
        entities.append(BoschFrigateUrlHighSensor(coordinator, cam_id, config_entry))
        entities.append(BoschFrigateUrlLowSensor(coordinator, cam_id, config_entry))
    async_add_entities(entities, update_before_add=False)


# ─────────────────────────────────────────────────────────────────────────────
class _BoschSensorBase(CoordinatorEntity, SensorEntity):  # type: ignore[misc]
    """Shared base for all Bosch camera sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry

        info = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title = info.get("title", cam_id)
        self._model = info.get("hardwareVersion", "CAMERA")
        from .models import get_display_name

        self._model_name = get_display_name(self._model)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

    @property
    def _cam_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._cam_id, {})  # type: ignore[no-any-return]

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": self._model_name,
            "sw_version": self._fw,
            "connections": {("mac", self._mac)} if self._mac else set(),
        }


# ─────────────────────────────────────────────────────────────────────────────
_STATUS_SENSOR_OPTIONS: list[str] = [
    "online",
    "offline",
    "updating",
    "session_limit",
    "unknown",
]


class BoschCameraStatusSensor(_BoschSensorBase):
    """Sensor: online / offline / updating / unknown.

    `updating` takes precedence over online/offline because the camera
    reboots during a firmware install and any cloud "online" reading is
    cached from before the reboot. Dashboard auto-entities and automations
    can use this single sensor to drive both visibility and alerting.
    """

    _attr_options: ClassVar[list[str]] = _STATUS_SENSOR_OPTIONS
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_status_{cam_id.lower()}"
        self._attr_translation_key = "status"

    @property
    def native_value(self) -> str:
        # Firmware install in progress trumps the cloud-cached status —
        # the camera is rebooting and dependent entities should reflect that.
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return "updating"
        raw = str(self._cam_data.get("status", "UNKNOWN")).lower()
        if raw == "online":
            events = self._cam_data.get("events", [])
            if (
                events
                and str(events[0].get("eventType", "")).upper() == "TROUBLE_DISCONNECT"
            ):
                return "offline"
        # session_limit: HTTP 444 — not offline, just too many concurrent sessions
        if raw == "session_limit":
            return "session_limit"
        return raw if raw in _STATUS_SENSOR_OPTIONS else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._cam_data.get("info", {})
        comm = self.coordinator._commissioned_cache.get(self._cam_id, {})
        fw = self.coordinator._firmware_cache.get(self._cam_id, {})
        attrs: dict[str, Any] = {
            "camera_id": self._cam_id,
            "model": info.get("hardwareVersion", ""),
            "firmware": info.get("firmwareVersion", ""),
            "mac": info.get("macAddress", ""),
        }
        if comm:
            attrs["configured"] = comm.get("configured")
            attrs["connected"] = comm.get("connected")
            attrs["commissioned"] = comm.get("commissioned")
        if fw:
            attrs["firmware_updating"] = fw.get("updating", False)
            attrs["firmware_update_status"] = fw.get("status", "")
            attrs["firmware_up_to_date"] = fw.get("upToDate", True)
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraLastEventSensor(_BoschSensorBase):
    """Sensor: datetime of the most recent motion event."""

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_last_event_{cam_id.lower()}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_translation_key = "last_event"

    @property
    def native_value(self) -> datetime | None:
        events = self._cam_data.get("events", [])
        if not events:
            return None
        ts_str = events[0].get("timestamp", "")
        if not ts_str:
            return None
        # Honor the offset Bosch sends ("+02:00" or "Z"); do NOT truncate it
        # away and re-label as UTC — that shifted the value +2h in CEST (#34).
        dt_utc = parse_bosch_timestamp(ts_str)
        if dt_utc is None:
            return None
        local_dt: datetime = dt_util.as_local(dt_utc)
        return local_dt

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = self._cam_data.get("events", [])
        latest = events[0] if events else {}
        return {
            "event_type": latest.get("eventType", ""),
            "event_id": latest.get("id", "")[:8],
            "has_image": bool(latest.get("imageUrl")),
            "has_clip": bool(latest.get("videoClipUrl")),
            "clip_status": latest.get("videoClipUploadStatus", ""),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraEventsTodaySensor(_BoschSensorBase):
    """Sensor: count of motion events that occurred today."""

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_events_today_{cam_id.lower()}"
        self._attr_native_unit_of_measurement = "events"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_key = "events_today"

    @property
    def native_value(self) -> int:
        events = self._cam_data.get("events", [])
        return sum(1 for ev in events if _event_is_today_local(ev.get("timestamp")))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = self._cam_data.get("events", [])
        today_events = [
            ev for ev in events if _event_is_today_local(ev.get("timestamp"))
        ]
        return {
            "events_in_feed": len(events),
            "latest_timestamps": [
                ev.get("timestamp", "")[:19] for ev in today_events[:5]
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschWifiSignalSensor(_BoschSensorBase):
    """Sensor: WiFi signal strength in percent.

    Data source: GET /v11/video_inputs/{id}/wifiinfo (fetched by coordinator).
    Attributes: ssid, ip_address, mac_address.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_wifi_signal_{cam_id.lower()}"
        # No device_class — Bosch API returns percentage (0-100), not dBm
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"
        self._attr_translation_key = "wifi_signal"

    @property
    def native_value(self) -> int | None:
        wifi = self.coordinator._wifiinfo_cache.get(self._cam_id)
        if wifi is None:
            return None
        signal = wifi.get("signalStrength")
        if signal is None:
            return None
        return int(signal)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._wifiinfo_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        wifi = self.coordinator._wifiinfo_cache.get(self._cam_id, {})
        attrs: dict[str, Any] = {
            "ssid": wifi.get("ssid", ""),
            "ip_address": wifi.get("ipAddress", ""),
            "mac_address": wifi.get("macAddress", ""),
        }
        lan_ip_rcp = self.coordinator.rcp_lan_ip(self._cam_id)
        if lan_ip_rcp:
            attrs["lan_ip_rcp"] = lan_ip_rcp
        ladder = self.coordinator.rcp_bitrate_ladder(self._cam_id)
        if ladder:
            attrs["bitrate_ladder_kbps"] = ladder
            attrs["max_bitrate_kbps"] = max(ladder)
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschFirmwareVersionSensor(_BoschSensorBase):
    """Sensor: firmware version string.

    Data source: firmwareVersion field from GET /v11/video_inputs (already in coordinator data).
    Attributes: up_to_date (bool from featureSupport.upToDate or similar field).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_firmware_{cam_id.lower()}"
        self._attr_translation_key = "firmware_version"

    @property
    def native_value(self) -> str | None:
        info = self._cam_data.get("info", {})
        fw = info.get("firmwareVersion", "")
        return fw if fw else None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self._cam_data.get("info", {}).get("firmwareVersion", "")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._cam_data.get("info", {})
        # upToDate may be a top-level field or inside featureSupport
        up_to_date = info.get("upToDate")
        if up_to_date is None:
            up_to_date = info.get("featureSupport", {}).get("upToDate")
        attrs: dict[str, Any] = {
            "up_to_date": up_to_date,
            "hardware_version": info.get("hardwareVersion", ""),
        }
        product_name = self.coordinator.rcp_product_name(self._cam_id)
        if product_name:
            attrs["product_name_rcp"] = product_name
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschAmbientLightSensor(_BoschSensorBase):
    """Sensor: ambient light level as a percentage (0–100%).

    Data source: GET /v11/video_inputs/{id}/ambient_light_sensor_level (fetched by coordinator).
    The API returns a float 0.0–1.0 which is converted to 0–100%.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_ambient_light_{cam_id.lower()}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"
        self._attr_translation_key = "ambient_light"

    @property
    def native_value(self) -> int | None:
        level = self.coordinator._ambient_light_cache.get(self._cam_id)
        if level is None:
            return None
        # Convert 0.0–1.0 float to 0–100 integer percentage
        return round(float(level) * 100)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._ambient_light_cache.get(self._cam_id) is not None
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschLedDimmerSensor(_BoschSensorBase):
    """Sensor: LED dimmer value 0–100% read via RCP protocol (command 0x0c22).

    Data source: RCP command 0x0c22 (T_WORD) via cloud proxy (rcp.xml).
    Only registered for cameras with featureSupport.light = True.
    State is None (unavailable) when RCP session could not be established.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_led_dimmer_{cam_id.lower()}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"
        self._attr_entity_registry_enabled_default = False
        self._attr_translation_key = "led_dimmer"

    @property
    def native_value(self) -> int | None:
        return self.coordinator._rcp_dimmer_cache.get(self._cam_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_dimmer_cache.get(self._cam_id) is not None
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschClockOffsetSensor(_BoschSensorBase):
    """Clock offset between camera internal clock and HA server (seconds)."""

    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_clock_offset"
        self._attr_translation_key = "clock_offset"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.clock_offset(self._cam_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.clock_offset(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.coordinator.clock_offset(self._cam_id)
        if val is None:
            return {}
        abs_offset = abs(val)
        if abs_offset < 5:
            status = "in_sync"
        elif abs_offset < 60:
            status = "minor_drift"
        else:
            status = "out_of_sync"
        return {
            "offset_seconds": val,
            "status": status,
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschMotionSensitivitySensor(_BoschSensorBase):
    """Shows motion detection enabled state and sensitivity level."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "motion_sensitivity"

    @property
    def name(self) -> str:
        return f"Bosch {self._cam_title} Motion Sensitivity"

    @property
    def unique_id(self) -> str:
        return f"bosch_shc_camera_{self._cam_id}_motion_sensitivity"

    @property
    def native_value(self) -> str | None:
        settings = self.coordinator.motion_settings(self._cam_id)
        if not settings:
            return None
        enabled = settings.get("enabled", False)
        if not enabled:
            return "disabled"
        return (
            str(settings.get("motionAlarmConfiguration", "UNKNOWN"))
            .lower()
            .replace("_", " ")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        settings = self.coordinator.motion_settings(self._cam_id)
        if not settings:
            return {}
        return {
            "enabled": settings.get("enabled"),
            "sensitivity": settings.get("motionAlarmConfiguration"),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschLastEventTypeSensor(_BoschSensorBase):
    """Shows the type of the most recent camera event."""

    _attr_translation_key = "last_event_type"
    _attr_options: ClassVar[list[str]] = [
        "movement",
        "person",
        "audio_alarm",
        "trouble",
        "trouble_disconnect",
        "trouble_reconnect",
        "trouble_connect",
        "none",
    ]
    _attr_device_class = SensorDeviceClass.ENUM

    @property
    def name(self) -> str:
        return f"Bosch {self._cam_title} Last Event Type"

    @property
    def unique_id(self) -> str:
        return f"bosch_shc_camera_{self._cam_id}_last_event_type"

    @property
    def native_value(self) -> str:
        events = self.coordinator.data.get(self._cam_id, {}).get("events", [])
        if not events:
            return "none"
        event_type = str(events[0].get("eventType", "")).lower()
        # ENUM device_class rejects any value outside _attr_options (HA logs a
        # state-validation warning and drops the state), so map a missing or
        # unrecognised event shape onto the "none" catch-all instead.
        return event_type if event_type in self._attr_options else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = self.coordinator.data.get(self._cam_id, {}).get("events", [])
        if not events:
            return {}
        latest = events[0]
        return {
            "event_type": latest.get("eventType"),
            "timestamp": latest.get("timestamp"),
            "event_id": latest.get("id"),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschMovementEventsTodaySensor(_BoschSensorBase):
    """Number of MOVEMENT events today."""

    _attr_native_unit_of_measurement = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "movement_events_today"

    @property
    def name(self) -> str:
        return f"Bosch {self._cam_title} Movement Events Today"

    @property
    def unique_id(self) -> str:
        return f"bosch_shc_camera_{self._cam_id}_movement_events_today"

    @property
    def native_value(self) -> int:
        events = self.coordinator.data.get(self._cam_id, {}).get("events", [])
        return sum(
            1
            for e in events
            if e.get("eventType") == "MOVEMENT"
            and _event_is_today_local(e.get("timestamp"))
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschAudioEventsTodaySensor(_BoschSensorBase):
    """Number of AUDIO_ALARM events today."""

    _attr_native_unit_of_measurement = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "audio_events_today"

    @property
    def name(self) -> str:
        return f"Bosch {self._cam_title} Audio Events Today"

    @property
    def unique_id(self) -> str:
        return f"bosch_shc_camera_{self._cam_id}_audio_events_today"

    @property
    def native_value(self) -> int:
        events = self.coordinator.data.get(self._cam_id, {}).get("events", [])
        return sum(
            1
            for e in events
            if e.get("eventType") == "AUDIO_ALARM"
            and _event_is_today_local(e.get("timestamp"))
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschFcmPushStatusSensor(_BoschSensorBase):
    """Shows the event detection method: FCM push (instant) or polling (fallback).

    States:
      - "fcm_push"  — FCM connected and receiving pushes (~2s event detection)
      - "polling"   — FCM disabled or failed, using interval-based polling
      - "disabled"  — FCM push not enabled in options
    """

    _attr_unique_id = "bosch_shc_camera_fcm_push_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "push_status"
    _attr_options: ClassVar[list[str]] = ["fcm_push", "polling", "disabled"]
    _attr_device_class = SensorDeviceClass.ENUM
    # `last_push_seconds_ago` is recomputed from a monotonic clock on every
    # property read, so it changes on every coordinator tick even while the
    # state stays "fcm_push". Recording it spawns a fresh `state_attributes`
    # row each tick and bloats the DB (HA#39). Keep it visible live, but never
    # historize it. See https://developers.home-assistant.io/blog/2023/09/20/
    # excluding-state-attributes-from-recording/.
    _unrecorded_attributes = frozenset({"last_push_seconds_ago"})

    @property
    def native_value(self) -> str:
        if not self.coordinator.options.get("enable_fcm_push", False):
            return "disabled"
        if self.coordinator._fcm_healthy:
            return "fcm_push"
        return "polling"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        import time as _time

        attrs: dict[str, Any] = {
            "fcm_enabled": self.coordinator.options.get("enable_fcm_push", False),
            "fcm_running": self.coordinator._fcm_running,
            "fcm_healthy": self.coordinator._fcm_healthy,
            "fcm_push_mode": self.coordinator._fcm_push_mode,
            "fcm_push_mode_config": self.coordinator.options.get(
                "fcm_push_mode", "auto"
            ),
        }
        if self.coordinator._fcm_last_push != float("-inf"):
            age = _time.monotonic() - self.coordinator._fcm_last_push
            attrs["last_push_seconds_ago"] = round(age)
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschCloudMaintenanceSensor(_BoschSensorBase):
    """Surfaces Bosch's announced maintenance / incident state for the cloud.

    Data source: community.bosch-smarthome.com Wartungsarbeiten + Statusmeldungen
    RSS feeds, fetched by the coordinator (see `maintenance.py`). One per
    integration. Stays available even when the Bosch cloud itself is down —
    that is the entire point: the user needs a stable place to see WHY their
    cameras are unavailable.
    """

    _attr_unique_id = "bosch_shc_camera_cloud_maintenance"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "cloud_maintenance"
    _attr_options: ClassVar[list[str]] = [
        "active",
        "scheduled",
        "past",
        "recent",
        "unknown",
        "idle",
    ]
    _attr_device_class = SensorDeviceClass.ENUM
    # `last_fetched_seconds_ago` is monotonic-derived → changes every tick.
    # Keep it live but unrecorded so it does not bloat `state_attributes`
    # (HA#39). The stable window fields (title/link/dates) stay recorded.
    _unrecorded_attributes = frozenset({"last_fetched_seconds_ago"})

    @property
    def available(self) -> bool:
        # Intentionally always True: the sensor must remain readable while the
        # Bosch cloud is down, since that is precisely when users look at it.
        return True

    @property
    def native_value(self) -> str:
        window = self.coordinator._maintenance_cache
        return window.state() if window else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        import time as _time

        window = self.coordinator._maintenance_cache
        attrs: dict[str, Any] = {}
        if window is not None:
            attrs.update(window.as_dict())
        last_fetch = self.coordinator._maintenance_last_fetch
        if last_fetch != float("-inf"):
            attrs["last_fetched_seconds_ago"] = round(_time.monotonic() - last_fetch)
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschUnreadEventsCountSensor(_BoschSensorBase):
    """Sensor: number of unread events for this camera.

    Data source: GET /v11/video_inputs/{id}/unread_events_count (fetched by coordinator, slow tier).
    Disabled by default — enable in HA entity settings if needed.
    """

    _attr_native_unit_of_measurement = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_unread_events"
        self._attr_translation_key = "unread_events"

    @property
    def native_value(self) -> int | None:
        return self.coordinator._unread_events_cache.get(self._cam_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._unread_events_cache.get(self._cam_id) is not None
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschCommissionedSensor(_BoschSensorBase):
    """Sensor: commissioned status from GET /v11/video_inputs/{id}/commissioned.

    Response: {"configured": true, "connected": true, "commissioned": true}
    Displays: "Commissioned" / "Not commissioned" / "Not connected"
    Diagnostic, disabled by default.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_commissioned"
        self._attr_translation_key = "commissioned"
        self._attr_options = ["commissioned", "not_commissioned", "not_connected"]
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str | None:
        data = self.coordinator._commissioned_cache.get(self._cam_id)
        if data is None:
            return None
        if not data.get("connected", False):
            return "not_connected"
        if data.get("commissioned", False):
            return "commissioned"
        return "not_commissioned"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._commissioned_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator._commissioned_cache.get(self._cam_id)
        if not data:
            return {}
        return {
            "configured": data.get("configured"),
            "connected": data.get("connected"),
            "commissioned": data.get("commissioned"),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschRulesCountSensor(_BoschSensorBase):
    """Sensor: number of cloud-side schedule rules for this camera.

    Data source: GET /v11/video_inputs/{id}/rules (fetched by coordinator, slow tier).
    Attributes: list of rule names and active status.
    """

    _attr_native_unit_of_measurement = "rules"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    # `rules` is a list of rule dicts purely for card display; recording it
    # spends a large `state_attributes` blob with zero history value (HA#39).
    _unrecorded_attributes = frozenset({"rules"})

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_rules_count"
        self._attr_translation_key = "schedule_rules"

    @property
    def native_value(self) -> int | None:
        rules = self.coordinator._rules_cache.get(self._cam_id)
        if rules is None:
            return None
        return len(rules)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rules_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rules = self.coordinator._rules_cache.get(self._cam_id, [])
        return {
            "rules": [
                {
                    "id": r.get("id", ""),
                    "name": r.get("name", ""),
                    "active": r.get("isActive", False),
                    "start": r.get("startTime", ""),
                    "end": r.get("endTime", ""),
                    "weekdays": r.get("weekdays", []),
                }
                for r in rules
            ],
        }


# ── Phase 2: RCP Deep Dive Sensors ──────────────────────────────────────────


class BoschAlarmCatalogSensor(_BoschSensorBase):
    """Sensor: alarm types supported by camera firmware (RCP 0x0c38).

    Displays count of supported alarm types. Attributes list all types
    with name and category (virtual, flame, smoke, audio, motion, etc.).
    """

    _attr_native_unit_of_measurement = "types"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    # `alarm_details` duplicates the full RCP catalog as a big list; keep the
    # small `alarm_types`/`categories` recorded but never the blob (HA#39).
    _unrecorded_attributes = frozenset({"alarm_details"})

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_catalog"
        self._attr_translation_key = "alarm_catalog"

    @property
    def native_value(self) -> int | None:
        alarms = self.coordinator._rcp_alarm_catalog_cache.get(self._cam_id)
        if alarms is None:
            return None
        return len(alarms)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_alarm_catalog_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alarms = self.coordinator._rcp_alarm_catalog_cache.get(self._cam_id, [])
        return {
            "alarm_types": [a["name"] for a in alarms],
            "alarm_details": alarms,
            "categories": list({a["type"] for a in alarms}),
        }


class BoschMotionZonesSensor(_BoschSensorBase):
    """Sensor: motion detection zones (Cloud API + RCP + Gen2 polygon zones).

    Displays total number of zones across all sources.
    Attributes contain zone data for overlay visualization:
      - cloud_zones: Gen1 rectangular zones (x/y/w/h normalized 0.0–1.0)
      - gen2_zones: Gen2 polygon zones (points array, trigger, color)
      - zones/coordinates: RCP firmware data (fallback)
    """

    _attr_native_unit_of_measurement = "zones"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Coordinate lists for card overlay only — never historize the blobs
    # (HA#39). The *_count fields stay recorded.
    _unrecorded_attributes = frozenset(
        {"zones", "coordinates", "cloud_zones", "gen2_zones"}
    )
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_zones"
        self._attr_translation_key = "motion_zones"

    @property
    def native_value(self) -> int | None:
        # Regression (bug-hunt 2026-07-03): unlike every sibling diagnostic
        # sensor in this file (BoschRulesCountSensor, BoschAlarmCatalogSensor,
        # etc.), this previously defaulted every cache lookup to `[]` and
        # returned `len([])` == 0 even before any of the 3 sources had ever
        # been fetched — reporting a confirmed "0 zones" state (with the
        # misleading "No motion zones configured" attribute note) instead of
        # unknown/unavailable during the window before the first successful
        # fetch, or on a camera where it never succeeds. Distinguish
        # "not yet fetched" (None) from "fetched, zero zones" ([]) per source.
        gen2_zones = self.coordinator._gen2_zones_cache.get(self._cam_id)
        cloud_zones = self.coordinator._cloud_zones_cache.get(self._cam_id)
        zones = self.coordinator._rcp_motion_zones_cache.get(self._cam_id)
        if gen2_zones is None and cloud_zones is None and zones is None:
            return None
        # Gen2 polygon zones take priority
        if gen2_zones:
            return len(gen2_zones)
        # Then cloud zones (Gen1 rectangles)
        if cloud_zones:
            return len(cloud_zones)
        # Fallback to RCP
        return len(zones or [])

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            self.coordinator._gen2_zones_cache.get(self._cam_id) is not None
            or self.coordinator._cloud_zones_cache.get(self._cam_id) is not None
            or self.coordinator._rcp_motion_zones_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zones = self.coordinator._rcp_motion_zones_cache.get(self._cam_id, [])
        coords = self.coordinator._rcp_motion_coords_cache.get(self._cam_id, [])
        cloud_zones = self.coordinator._cloud_zones_cache.get(self._cam_id, [])
        gen2_zones = self.coordinator._gen2_zones_cache.get(self._cam_id, [])
        attrs: dict[str, Any] = {
            "zones": zones,
            "coordinates": coords,
            "coordinate_count": len(coords),
            "cloud_zones": cloud_zones,
            "cloud_zone_count": len(cloud_zones),
            "gen2_zones": gen2_zones,
            "gen2_zone_count": len(gen2_zones),
        }
        total = len(gen2_zones) or len(cloud_zones) or len(zones)
        if total == 0:
            attrs["note"] = (
                "No motion zones configured — use the Bosch app to set up zones"
            )
        return attrs


class BoschTlsCertSensor(_BoschSensorBase):
    """Sensor: TLS certificate info from camera (RCP 0x0b91).

    Displays certificate expiry date. Attributes contain issuer, subject,
    key size, and serial number.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_tls_cert"
        self._attr_translation_key = "tls_cert"

    @property
    def native_value(self) -> datetime | None:
        cert = self.coordinator._rcp_tls_cert_cache.get(self._cam_id)
        if not cert or "not_after" not in cert:
            return None
        try:
            dt = datetime.fromisoformat(cert["not_after"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_tls_cert_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cert = self.coordinator._rcp_tls_cert_cache.get(self._cam_id, {})
        return {
            "issuer": cert.get("issuer", ""),
            "subject": cert.get("subject", ""),
            "key_size": cert.get("key_size"),
            "serial": cert.get("serial", ""),
            "not_before": cert.get("not_before", ""),
            "not_after": cert.get("not_after", ""),
            "signature_algorithm": cert.get("signature_algorithm", ""),
        }


class BoschNetworkServicesSensor(_BoschSensorBase):
    """Sensor: network services running on camera (RCP 0x0c62).

    Displays count of active services. Attributes list all services
    (HTTP, HTTPS, RTSP, SNMP, UPnP, NTP, ONVIF, etc.).
    """

    _attr_native_unit_of_measurement = "services"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_network_services"
        self._attr_translation_key = "network_services"

    @property
    def native_value(self) -> int | None:
        services = self.coordinator._rcp_network_services_cache.get(self._cam_id)
        if services is None:
            return None
        return len(services)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_network_services_cache.get(self._cam_id)
            is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        services = self.coordinator._rcp_network_services_cache.get(self._cam_id, [])
        return {"services": services}


class BoschIvaCatalogSensor(_BoschSensorBase):
    """Sensor: IVA analytics modules from camera firmware (RCP 0x0b60).

    Displays count of analytics modules. Attributes list all modules with
    ID, version, flags, and active state.
    """

    _attr_native_unit_of_measurement = "modules"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    # Module lists for card display only — never historize the blobs (HA#39).
    # `active_count` stays recorded.
    _unrecorded_attributes = frozenset({"modules", "active_modules"})

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_iva_catalog"
        self._attr_translation_key = "iva_analytics"

    @property
    def native_value(self) -> int | None:
        modules = self.coordinator._rcp_iva_catalog_cache.get(self._cam_id)
        if modules is None:
            return None
        return len(modules)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_iva_catalog_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        modules = self.coordinator._rcp_iva_catalog_cache.get(self._cam_id, [])
        active = [m for m in modules if m.get("active")]
        return {
            "modules": modules,
            "active_count": len(active),
            "active_modules": active,
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschPrivateAreasSensor(_BoschSensorBase):
    """Sensor: privacy mask areas (Gen1 rectangles + Gen2 polygons).

    Displays number of privacy masks. Attributes contain mask data
    for overlay visualization on the camera image.
      - cloud_privacy_masks: Gen1 rectangular masks (x/y/w/h normalized 0.0–1.0)
      - gen2_private_areas: Gen2 polygon masks (points array, color)
    """

    _attr_native_unit_of_measurement = "masks"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    # Mask coordinate lists for card overlay only — never historize the blobs
    # (HA#39). The *_count fields stay recorded.
    _unrecorded_attributes = frozenset({"cloud_privacy_masks", "gen2_private_areas"})

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_privacy_masks"
        self._attr_translation_key = "privacy_masks"

    @property
    def native_value(self) -> int | None:
        # Regression (bug-hunt 2026-07-03): see BoschMotionZonesSensor —
        # this defaulted both cache lookups to `[]` and returned a
        # confirmed "0 masks" (with a misleading "no masks configured"
        # attribute note) even before either source had ever been fetched.
        gen2_areas = self.coordinator._gen2_private_areas_cache.get(self._cam_id)
        cloud_masks = self.coordinator._cloud_privacy_masks_cache.get(self._cam_id)
        if gen2_areas is None and cloud_masks is None:
            return None
        # Gen2 polygon private areas take priority
        if gen2_areas:
            return len(gen2_areas)
        # Gen1 cloud privacy masks
        return len(cloud_masks or [])

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            self.coordinator._gen2_private_areas_cache.get(self._cam_id) is not None
            or self.coordinator._cloud_privacy_masks_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cloud_masks = self.coordinator._cloud_privacy_masks_cache.get(self._cam_id, [])
        gen2_areas = self.coordinator._gen2_private_areas_cache.get(self._cam_id, [])
        attrs: dict[str, Any] = {
            "cloud_privacy_masks": cloud_masks,
            "cloud_mask_count": len(cloud_masks),
            "gen2_private_areas": gen2_areas,
            "gen2_area_count": len(gen2_areas),
        }
        total = len(gen2_areas) or len(cloud_masks)
        if total == 0:
            attrs["note"] = (
                "No privacy masks configured — use the Bosch app to set up masks"
            )
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschAmbientLightScheduleSensor(_BoschSensorBase):
    """Sensor: ambient light schedule details (Gen2 only).

    Shows the schedule mode (ENVIRONMENT = dusk-to-dawn, or manual times).
    Attributes contain the full schedule config: enabled state, schedule type,
    manual start/end times, and per-light-group brightness/whiteBalance settings.
    Data source: GET /v11/video_inputs/{id}/lighting/ambient (fetched by coordinator, slow tier).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_ambient_schedule"
        self._attr_translation_key = "ambient_schedule"
        self._attr_options = ["disabled", "dusk_to_dawn", "manual"]
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str | None:
        cache = self.coordinator._ambient_lighting_cache.get(self._cam_id)
        if not cache:
            return None
        enabled = cache.get("ambientLightEnabled", False)
        if not enabled:
            return "disabled"
        schedule = cache.get("ambientLightSchedule", {})
        # Schedule can be a string ("ENVIRONMENT") or dict ({"type": "ENVIRONMENT", ...})
        schedule_type = (
            schedule.get("type", schedule) if isinstance(schedule, dict) else schedule
        )
        if schedule_type == "ENVIRONMENT":
            return "dusk_to_dawn"
        return "manual"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._ambient_lighting_cache.get(self._cam_id) is not None
            and len(self.coordinator._ambient_lighting_cache.get(self._cam_id, {})) > 0
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cache = self.coordinator._ambient_lighting_cache.get(self._cam_id, {})
        if not cache:
            return {}
        schedule = cache.get("ambientLightSchedule", "ENVIRONMENT")
        if isinstance(schedule, dict):
            schedule_str = schedule.get("type", "ENVIRONMENT")
        else:
            schedule_str = schedule
        attrs: dict[str, Any] = {
            "enabled": cache.get("ambientLightEnabled", False),
            "schedule_type": schedule_str,
        }
        if isinstance(schedule, dict):
            if schedule.get("lightOnTime"):
                attrs["schedule_on_time"] = schedule["lightOnTime"]
            if schedule.get("lightOffTime"):
                attrs["schedule_off_time"] = schedule["lightOffTime"]
        # Manual schedule times (if set)
        start = cache.get("ambientLightManualStartTime")
        end = cache.get("ambientLightManualEndTime")
        if start:
            attrs["manual_start_time"] = start
        if end:
            attrs["manual_end_time"] = end
        # Per-light-group brightness settings
        for group_key in (
            "frontLightSettings",
            "topLedLightSettings",
            "bottomLedLightSettings",
        ):
            group = cache.get(group_key)
            if group and isinstance(group, dict):
                prefix = (
                    group_key.replace("Settings", "")
                    .replace("Light", "_light")
                    .replace("Led", "_led")
                )
                attrs[f"{prefix}_brightness"] = group.get("brightness")
                wb = group.get("whiteBalance")
                if wb is not None:
                    attrs[f"{prefix}_white_balance"] = wb
                color = group.get("color")
                if color is not None:
                    attrs[f"{prefix}_color"] = color
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
class BoschAlarmStateSensor(_BoschSensorBase):
    """Sensor: alarm state (Gen2 Indoor II only).

    Actual API response (confirmed 2026-04-11):
        GET /v11/video_inputs/{id}/alarmStatus
        → {"alarmType": "NONE" | ..., "intrusionSystem": "INACTIVE" | "ACTIVE" | ...}

    Sensor state = intrusionSystem field (INACTIVE = disarmed, ACTIVE = armed).
    `alarm_type` in attributes exposes what kind of alarm last fired (NONE when idle).
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_state"
        self._attr_translation_key = "alarm_state"
        self._attr_options = [
            "active",
            "inactive",
            "unknown",
            "system_managed_armed",
            "system_managed_disarmed",
            "armed_away",
            "armed_stay",
            "disarmed",
        ]
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str:
        status = self.coordinator._alarm_status_cache.get(self._cam_id, {})
        if status:
            # Guard the ENUM: an unmapped intrusionSystem value (e.g. new
            # firmware) would make HA discard the state and show "unknown"
            # anyway — map it explicitly so alarm automations get a defined
            # value, not a dropped one (same pattern as BoschLastEventTypeSensor).
            val = str(status.get("intrusionSystem", "unknown")).lower()
            opts = getattr(self, "_attr_options", None)
            return val if (not opts or val in opts) else "unknown"
        armed = self.coordinator._arming_cache.get(self._cam_id)
        if armed is True:
            return "active"
        if armed is False:
            return "inactive"
        return "unknown"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        settings = self.coordinator._alarm_settings_cache.get(self._cam_id, {})
        status = self.coordinator._alarm_status_cache.get(self._cam_id, {})
        return {
            "alarm_mode": settings.get("alarmMode"),
            "pre_alarm_mode": settings.get("preAlarmMode"),
            "siren_duration_s": settings.get("alarmDelayInSeconds"),
            "activation_delay_s": settings.get("alarmActivationDelaySeconds"),
            "pre_alarm_duration_s": settings.get("preAlarmDelayInSeconds"),
            "alarm_type": status.get("alarmType"),
            "intrusion_system": status.get("intrusionSystem"),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschStreamStatusSensor(_BoschSensorBase):
    """Sensor: live stream state — idle / warming_up / connecting / streaming / streaming_remote."""

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_stream_status_{cam_id.lower()}"
        self._attr_translation_key = "stream_status"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_options = [
            "idle",
            "warming_up",
            "connecting",
            "streaming",
            "streaming_remote",
        ]
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str:
        fell_back = self.coordinator._stream_fell_back.get(self._cam_id, False)
        if self.coordinator.is_stream_warming(self._cam_id):
            return "warming_up"
        live = self.coordinator._live_connections.get(self._cam_id, {})
        rtsps = live.get("rtspsUrl") or live.get("rtspUrl")
        if rtsps:
            # stream_source is set → FFmpeg is (or will be) playing
            if fell_back:
                return "streaming_remote"
            return "streaming"
        if self._cam_id in self.coordinator._live_connections:
            return "connecting"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        live = self.coordinator._live_connections.get(self._cam_id, {})
        return {
            "connection_type": live.get("_connection_type", ""),
            "stream_errors": self.coordinator._stream_error_count.get(self._cam_id, 0),
            "fell_back": self.coordinator._stream_fell_back.get(self._cam_id, False),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschNvrStateSensor(_BoschSensorBase):
    """Diagnostic sensor surfacing the Mini-NVR drain-watcher state per camera.

    Helps users answer "is recording actually reaching the target?". Reads
    from ``coordinator._nvr_drain_state`` (populated by
    ``recorder.sync_drain_tick``) and ``coordinator._nvr_user_intent`` /
    ``coordinator._nvr_processes`` (populated by the recorder lifecycle
    plumbing). Pure properties — no I/O. Disabled by default in the entity
    registry to avoid surprise entities.

    States:
      * ``recording`` — ffmpeg child is alive AND user-intent flag is set
      * ``idle``      — no recorder is running for this camera
      * ``error``     — the crash-loop guard tripped

    Attributes:
      * ``target``             — current ``nvr_storage_target`` (local/smb/ftp)
      * ``pending_uploads``    — files in the staging tree not yet finalized
      * ``failed_uploads``     — failed-this-tick upload count
      * ``last_segment_age_s`` — seconds since last seen segment for this cam
    """

    _attr_entity_registry_enabled_default = False
    # These fields are recomputed every 30 s drain tick while recording, so
    # they churn the recorder with no history value (HA#39). Keep them live;
    # never historize them. `target`/`error`/`user_intent` stay recorded.
    _unrecorded_attributes = frozenset(
        {"last_segment_age_s", "last_tick_ts", "pending_uploads", "failed_uploads"}
    )

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_nvr_state_{cam_id.lower()}"
        self._attr_translation_key = "nvr_state"
        self._attr_options = ["idle", "recording", "error"]
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str:
        if self.coordinator._nvr_error_state.get(self._cam_id):
            return "error"
        proc = self.coordinator._nvr_processes.get(self._cam_id)
        if proc is not None and self.coordinator._nvr_user_intent.get(self._cam_id):
            return "recording"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = getattr(self.coordinator, "_nvr_drain_state", {}) or {}
        # Camera title is used as the staging-folder key (sanitized via
        # _safe_name in recorder._staging_dir). Read with the same sanitization
        # so the per-camera age lookup stays consistent.
        from .smb import _safe_name

        info = self.coordinator.data.get(self._cam_id, {}).get("info", {})
        cam_key = _safe_name(info.get("title", self._cam_id))
        last_age = (state.get("last_age_by_cam") or {}).get(cam_key)
        preroll_count = self.coordinator._nvr_preroll_segment_counts.get(
            self._cam_id, 0
        )
        return {
            "target": state.get("target", "local"),
            "pending_uploads": int(state.get("pending", 0)),
            "failed_uploads": int(state.get("failed", 0)),
            "last_segment_age_s": float(last_age) if last_age is not None else None,
            "last_tick_ts": state.get("last_tick_ts"),
            "user_intent": bool(
                self.coordinator._nvr_user_intent.get(self._cam_id, False)
            ),
            "error": self.coordinator._nvr_error_state.get(self._cam_id, ""),
            "preroll_segments": preroll_count,
            "preroll_running": bool(
                self.coordinator._nvr_preroll_processes.get(self._cam_id)
            ),
        }


class BoschCameraAiDescriptionSensor(_BoschSensorBase):
    """Sensor: last AI-generated snapshot description for this camera.

    Only created when the ``enable_ai_description`` integration option is
    enabled.  The state is the description text, truncated to 255 chars
    (HA state hard limit).  The full text is available in
    ``extra_state_attributes["description"]``.

    Updated via coordinator push whenever :func:`handle_describe_snapshot`
    stores a new result in ``coordinator.data[cam_id]["ai_description"]``.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_ai_description_{cam_id.lower()}"
        self._attr_translation_key = "ai_description"

    @property
    def native_value(self) -> str | None:
        """Return last description, truncated to 255 chars (HA state limit)."""
        text: str | None = self._cam_data.get("ai_description", {}).get("text")
        if text is None:
            return None
        return text[:255]

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose full description + metadata."""
        ai: dict[str, str | None] = self._cam_data.get("ai_description", {})
        return {
            "description": ai.get("text"),
            "generated_at": ai.get("generated_at"),
            "ai_task_entity": ai.get("ai_task_entity"),
        }


# ─────────────────────────────────────────────────────────────────────────────
import re as _re_inst


def _swap_inst(url: str, new_inst: int) -> str:
    """Return ``url`` with its ``inst=N`` query parameter rewritten to ``new_inst``.

    The Bosch RTSP URL always contains exactly one ``inst=N`` token in the
    query string (e.g. ``?inst=1&enableaudio=1``). This helper is the only
    place that knows that invariant — kept tiny so it's trivial to test.
    """
    return _re_inst.sub(r"inst=\d+", f"inst={new_inst}", url, count=1)


class _BoschStreamUrlSensorBase(_BoschSensorBase):
    """Shared base for the main + sub external-stream-URL sensors.

    Subclasses set ``_inst`` (1 for main, 2 for sub) and a translation key.
    Returns ``None`` when:
      - the BoschExternalStreamSwitch is OFF for this camera (default), OR
      - no live session is open yet (rtspsUrl empty).

    The URL is read straight from ``coordinator._live_connections[cam_id]``
    so it always reflects whatever quality/transport the integration picked
    (LOCAL TLS proxy, REMOTE TLS proxy, or direct rtsps fallback).
    """

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:link-variant"
    _inst: int = 1

    @property
    def native_value(self) -> str | None:
        if not self.coordinator._external_stream_enabled.get(self._cam_id, False):
            return None
        live = self.coordinator._live_connections.get(self._cam_id) or {}
        url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
        if not url:
            return None
        # The integration always picks one ``inst=N`` per session; for the
        # sub-stream sensor we substitute it with 2. For the main sensor we
        # leave it untouched (whatever the user picked in options is fine —
        # typically inst=1 for max quality on LOCAL).
        if self._inst == 2:
            return _swap_inst(url, 2)
        return url


class BoschStreamUrlSensor(_BoschStreamUrlSensorBase):
    """Main RTSP stream URL (whatever inst= the current session uses).

    Default quality is inst=1 (LOCAL ~30 Mbps full-HD); selectable via the
    integration's stream-connection options. Same URL the camera entity uses
    internally — exposing it here lets users paste it into Frigate / BlueIris
    without digging through HA's internals.
    """

    _inst = 1

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_stream_url_{cam_id.lower()}"
        self._attr_translation_key = "stream_url"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC


class BoschStreamUrlSubSensor(_BoschStreamUrlSensorBase):
    """Sub-stream RTSP URL (inst=2 — balanced quality, ~7.5 Mbps LOCAL).

    Derived from the main URL by substituting ``inst=N`` → ``inst=2``. Same
    Bosch session, same TLS proxy, no extra cloud-API quota cost — RTSP is
    pull-based, so the camera only sends the sub-stream when an external
    client actually connects.
    """

    _inst = 2

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_stream_url_sub_{cam_id.lower()}"
        self._attr_translation_key = "stream_url_sub"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC


class _BoschFrigateUrlSensorBase(_BoschSensorBase):
    """Credential-free always-on RTSP URL for an external recorder (Frigate).

    Returns None unless the global ``frigate_endpoints_enabled`` option is on,
    the matching per-camera High/Low switch is on, and the front-door is bound.
    The URL needs no ``user:pass@`` — the front-door injects Digest auth toward
    the camera. Paste it straight into Frigate's go2rtc / ffmpeg input.
    """

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cctv"
    _quality: str = "high"

    @property
    def native_value(self) -> str | None:
        url: str | None = self.coordinator.frigate_endpoint_url(
            self._cam_id, self._quality
        )
        return url


class BoschFrigateUrlHighSensor(_BoschFrigateUrlSensorBase):
    """Frigate persistent endpoint URL — High quality (inst=1)."""

    _quality = "high"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_frigate_url_high_{cam_id.lower()}"
        self._attr_translation_key = "frigate_url_high"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC


class BoschFrigateUrlLowSensor(_BoschFrigateUrlSensorBase):
    """Frigate persistent endpoint URL — Low quality (inst=2)."""

    _quality = "low"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_frigate_url_low_{cam_id.lower()}"
        self._attr_translation_key = "frigate_url_low"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC


# ─────────────────────────────────────────────────────────────────────────────
# F4: ONVIF Scopes Sensor
# ─────────────────────────────────────────────────────────────────────────────


class BoschOnvifScopesSensor(_BoschSensorBase):
    """Sensor: ONVIF scope advertisement from camera firmware (RCP 0x0a98 via LAN).

    State: "ONVIF supported" when the camera answered the LAN RCP read, else
    the entity stays unavailable. Attributes contain the parsed scope dict
    (camera name, hardware model, advertised ONVIF profiles).

    Data source: RCP command 0x0a98 read directly from cam:443 over HTTPS
    with Digest auth (cbs credentials from _local_creds_cache). Slow-tier
    (300 s) — cbs creds rotate on every PUT /connection so the RCP read
    is always authenticated with fresh credentials from the last LAN session.

    Disabled by default — enable in HA entity settings.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_options: ClassVar[list[str]] = ["supported"]
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_onvif_scopes"
        self._attr_translation_key = "onvif_scopes"

    @property
    def native_value(self) -> str | None:
        scopes = self.coordinator._rcp_onvif_scopes_cache.get(self._cam_id)
        if not scopes:
            return None
        return "supported"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_onvif_scopes_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scopes = self.coordinator._rcp_onvif_scopes_cache.get(self._cam_id, {})
        return {
            "name": scopes.get("name", ""),
            "hardware": scopes.get("hardware", ""),
            "profiles": scopes.get("profiles", []),
            "raw_scopes": scopes.get("raw_scopes", []),
        }


# ─────────────────────────────────────────────────────────────────────────────
# F6: RCP Version Sensor
# ─────────────────────────────────────────────────────────────────────────────


class BoschRcpVersionSensor(_BoschSensorBase):
    """Sensor: RCP protocol version from camera firmware (RCP 0xff00 via LAN).

    State: version string "major.minor.patch.build" (e.g. "1.2.38.150").
    Gen1 cameras report ~1.2.9.225; Gen2 FW 9.40.102 reports 1.2.38.150.

    Data source: RCP command 0xff00 read directly from cam:443 over HTTPS
    with Digest auth (cbs credentials from _local_creds_cache). Slow-tier
    (300 s). Returns 4 bytes which map to the four version components.

    Disabled by default — enable in HA entity settings.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_rcp_version"
        self._attr_translation_key = "rcp_version"

    @property
    def native_value(self) -> str | None:
        return self.coordinator._rcp_version_cache.get(self._cam_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator._rcp_version_cache.get(self._cam_id) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ver = self.coordinator._rcp_version_cache.get(self._cam_id, "")
        if not ver:
            return {}
        parts = ver.split(".")
        return {
            "major": parts[0] if len(parts) > 0 else "",
            "minor": parts[1] if len(parts) > 1 else "",
            "patch": parts[2] if len(parts) > 2 else "",
            "build": parts[3] if len(parts) > 3 else "",
        }


# ─────────────────────────────────────────────────────────────────────────────
# F13: Cloud Feature Flags Sensor
# ─────────────────────────────────────────────────────────────────────────────


class BoschCloudFeatureFlagsSensor(_BoschSensorBase):
    """Sensor: Bosch cloud feature flags for this account (GET /v11/feature_flags).

    State: comma-separated list of enabled flag names (those with value=True).
    Attributes: full dict of all flags with their boolean values.

    Data source: GET /v11/feature_flags — fetched once at startup and cached
    in coordinator._feature_flags. Rarely changes (account-level server-side
    config). Account-level entity — one per integration, not per camera.

    Disabled by default — enable in HA entity settings.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        # Account-level unique_id — not per camera
        self._attr_unique_id = "bosch_shc_camera_cloud_feature_flags"
        self._attr_translation_key = "cloud_feature_flags"

    @property
    def native_value(self) -> str | None:
        flags = self.coordinator._feature_flags
        if not flags:
            return None
        enabled = sorted(k for k, v in flags.items() if v)
        result = ", ".join(enabled) if enabled else "none"
        return result[:255]

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator._feature_flags
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        flags = self.coordinator._feature_flags
        if not flags:
            return {}
        return dict(flags)
