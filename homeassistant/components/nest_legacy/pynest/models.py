# ruff: noqa: N815
"""Models used by PyNest."""

from __future__ import annotations

from dataclasses import dataclass, fields
import datetime
from typing import Any

from .enums import (
    HotWaterMode,
    LockBoltActor,
    LockBoltState,
    StructureMode,
    TemperatureScale,
    ThermostatHvacMode,
    ThermostatHvacState,
)


# --- Base/Common Models ---
@dataclass(frozen=True)
class NestDevice:
    """Base class for a Nest device."""

    object_key: str
    serial_number: str
    name: str
    model: str | None = None
    software_version: str | None = None
    online: bool = True
    location: str | None = None
    mac_address: str | None = None
    is_protobuf: bool = False
    battery_voltage: float | None = None

    @property
    def hardware_version(self) -> str | None:
        """Return hardware version if available."""
        return None


# --- Specific Device Models ---
@dataclass(frozen=True)
class NestProtect(NestDevice):
    """Represents a Nest Protect smoke/CO alarm."""

    smoke_status: bool = False
    co_status: bool = False
    heat_status: bool = False
    battery_level: float = 0.0
    battery_health_state: int = 0
    replace_by_date: datetime.date | None = None
    night_light_enable: bool = False
    steam_detection_enable: bool = False
    night_light_brightness: int | None = None
    # Diagnostic / Config Attributes
    component_speaker_test_passed: bool = False
    component_smoke_test_passed: bool = False
    component_co_test_passed: bool = False
    component_wifi_test_passed: bool = False
    component_led_test_passed: bool = False
    component_pir_test_passed: bool = False
    component_buzzer_test_passed: bool = False
    component_hum_test_passed: bool = False
    removed_from_base: bool = False
    latest_manual_test_end_utc_secs: int = 0
    last_audio_self_test_end_utc_secs: int = 0
    ntp_green_led_enable: bool = False
    heads_up_enable: bool = False


@dataclass(frozen=True)
class NestWiredProtect(NestProtect):
    """Represents a wired Nest Protect."""

    occupancy: bool = False
    line_power_present: bool = False

    @property
    def hardware_version(self) -> str | None:
        """Return hardware version."""
        return "Wired"


@dataclass(frozen=True)
class NestBatteryProtect(NestProtect):
    """Represents a battery-powered Nest Protect."""

    @property
    def hardware_version(self) -> str | None:
        """Return hardware version."""
        return "Battery"


@dataclass(frozen=True)
class NestThermostat(NestDevice):
    """Represents a Nest Thermostat."""

    temperature_scale: TemperatureScale | None = None
    current_temperature: float | None = None
    backplate_temperature: float | None = None
    target_temperature: float | None = None
    target_temperature_low: float | None = None
    target_temperature_high: float | None = None
    current_humidity: int | None = None
    target_humidity: float | None = None
    hvac_state: ThermostatHvacState = ThermostatHvacState.OFF
    hvac_mode: ThermostatHvacMode = ThermostatHvacMode.OFF
    is_eco_mode: bool = False
    can_heat: bool = False
    can_cool: bool = False
    has_fan: bool = False
    fan_state: bool = False
    fan_timer_speed: int = 1
    fan_max_speed: int = 1
    fan_duration: int = 900
    fan_timer_timeout: int = 0
    has_dehumidifier: bool = False
    dehumidifier_state: bool = False
    occupancy: bool = False
    battery_level: float = 0.0
    leaf: bool = False
    temperature_lock: bool = False
    # Heat Link properties for derived device
    has_hot_water_control: bool = False
    heat_link_model: str | None = None
    heat_link_serial_number: str | None = None
    heat_link_sw_version: str | None = None
    hot_water_active: bool = False
    has_hot_water_temperature: bool = False
    hot_water_mode: HotWaterMode = HotWaterMode.OFF
    hot_water_away_enabled: bool = False
    hot_water_boost_time_to_end: int = 0
    hot_water_temperature: float | None = None
    current_water_temperature: float | None = None
    has_humidifier: bool = False
    humidifier_state: bool = False
    has_air_filter: bool = False
    filter_replacement_needed: bool | None = None
    filter_runtime: int | None = None


@dataclass(frozen=True)
class NestTempSensor(NestDevice):
    """Represents a Nest Temperature Sensor."""

    current_temperature: float | None = None
    battery_level: float = 0.0
    associated_thermostat_object_key: str | None = None
    is_active_sensor: bool = False


@dataclass(frozen=True)
class NestCamera(NestDevice):
    """Represents a Nest Camera."""

    streaming_enabled: bool = False
    audio_enabled: bool = False
    is_streaming: bool = False
    irled_enabled: bool = False
    status_led_enabled: bool = False
    video_flipped: bool = False
    web_url: str | None = None
    nexus_api_http_server_url: str | None = None
    structure_id: str | None = None
    battery_level: float | None = None


@dataclass(frozen=True)
class NestDoorbell(NestCamera):
    """Represents a Nest Doorbell."""

    indoor_chime_enabled: bool = False
    doorbell_chime_assist_enabled: bool = False
    has_indoor_chime: bool = False


@dataclass(frozen=True)
class NestHeatLink(NestDevice):
    """Represents a Nest Heat Link (for hot water control)."""

    associated_thermostat_object_key: str | None = None
    has_hot_water_control: bool = False
    hot_water_active: bool = False
    has_hot_water_temperature: bool = False
    hot_water_boost_time_to_end: int = 0
    hot_water_mode: HotWaterMode = HotWaterMode.OFF
    hot_water_away_enabled: bool = False
    current_temperature: float | None = None
    target_temperature: float | None = None
    temperature_scale: TemperatureScale | None = None


@dataclass(frozen=True)
class NestStructure(NestDevice):
    """Represents a Nest Structure (i.e., a home)."""

    mode: StructureMode = StructureMode.HOME


@dataclass(frozen=True)
class NestLock(NestDevice):
    """Represents a Nest x Yale Lock."""

    bolt_state: LockBoltState = LockBoltState.UNKNOWN
    bolt_actor: LockBoltActor | None = None
    battery_level: float = 0.0
    tampered: bool = False
    auto_relock_on: bool = False
    auto_relock_duration: int = 0
    max_auto_relock_duration: int = 300


# --- Raw API Response Models ---
@dataclass(frozen=True)
class NestEnvironment:
    """Class to describe a Nest environment."""

    host: str
    camera_host: str
    camera_cookie_name: str
    grpc_host: str


@dataclass(frozen=True)
class NestLimits:
    """Nest Limits."""

    thermostats_per_structure: int
    structures: int
    smoke_detectors_per_structure: int
    smoke_detectors: int
    thermostats: int


@dataclass(frozen=True)
class NestUrls:
    """Nest Urls."""

    rubyapi_url: str
    czfe_url: str
    log_upload_url: str
    transport_url: str
    weather_url: str
    support_url: str
    direct_transport_url: str


@dataclass
class NestSession:
    """Class that reflects a Nest API response."""

    access_token: str
    email: str
    expires_in: str
    userid: str
    user: str
    urls: NestUrls
    limits: NestLimits
    is_superuser: bool | None = None
    language: str | None = None
    is_staff: bool | None = None
    _2fa_state: str | None = None
    _2fa_enabled: bool | None = None
    _2fa_state_changed: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NestSession:
        """Create an instance from a dict, handling key remapping."""
        data = data.copy()
        if "2fa_state" in data:
            data["_2fa_state"] = data.pop("2fa_state")
        if "2fa_enabled" in data:
            data["_2fa_enabled"] = data.pop("2fa_enabled")
        if "2fa_state_changed" in data:
            data["_2fa_state_changed"] = data.pop("2fa_state_changed")

        known_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}

        if "urls" in filtered_data:
            filtered_data["urls"] = NestUrls(**filtered_data["urls"])
        if "limits" in filtered_data:
            filtered_data["limits"] = NestLimits(**filtered_data["limits"])

        return cls(**filtered_data)

    def is_expired(self) -> bool:
        """Check if session is expired."""
        try:
            expires_in_str = self.expires_in.removesuffix(" GMT")
            expiry_date = datetime.datetime.strptime(
                expires_in_str, "%a, %d-%b-%Y %H:%M:%S"
            ).replace(tzinfo=datetime.UTC)
            return expiry_date <= datetime.datetime.now(datetime.UTC)
        except ValueError, AttributeError:
            return False


@dataclass
class Bucket:
    """Class that reflects a Nest API bucket."""

    object_key: str
    object_revision: int
    object_timestamp: int
    value: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bucket:
        """Create an instance from a dict, ignoring unknown keys."""
        known_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


@dataclass
class FirstDataAPIResponse:
    """Response from the initial app_launch endpoint."""

    updated_buckets: list[Bucket]
    _2fa_enabled: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstDataAPIResponse:
        """Create an instance from a dict, handling key remapping."""
        data = data.copy()
        if "2fa_enabled" in data:
            data["_2fa_enabled"] = data.pop("2fa_enabled")
        return cls(
            updated_buckets=[
                Bucket.from_dict(b) for b in data.get("updated_buckets", []) if b
            ],
            _2fa_enabled=data.get("_2fa_enabled"),
        )


@dataclass
class GoogleAuthResponse:
    """Class that reflects a Google Auth response."""

    access_token: str
    scope: str
    token_type: str
    expires_in: int
    id_token: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoogleAuthResponse:
        """Create an instance from a dict, ignoring unknown keys."""
        known_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)


@dataclass
class NestAuthClaims:
    """Claims within a Nest JWT."""

    subject: Any | None = None
    expirationTime: str | None = None
    policyId: str | None = None
    structureConstraint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NestAuthClaims:
        """Create an instance from a dict, ignoring unknown keys."""
        known_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


@dataclass
class NestAuthResponse:
    """Response from the Nest JWT endpoint."""

    jwt: str | None = None
    claims: NestAuthClaims | dict[str, Any] | None = None

    def __post_init__(self):
        """Handle nested dataclass."""
        if self.claims and isinstance(self.claims, dict):
            self.claims = NestAuthClaims.from_dict(self.claims)
