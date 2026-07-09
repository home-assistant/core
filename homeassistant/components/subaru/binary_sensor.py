"""Support for Subaru binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    GEN_2_AND_NEWER,
    VEHICLE_API_GEN,
    VEHICLE_FEATURES,
    VEHICLE_HAS_EV,
    VEHICLE_HEALTH,
    VEHICLE_STATUS,
    VEHICLE_VIN,
)
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator
from .entity import SubaruCoordinatorEntity

# Keys returned by subarulink controller.get_data() inside vehicle_status
DOOR_POSITION_KEYS: dict[str, str] = {
    "DOOR_FRONT_LEFT_POSITION": "door_front_left",
    "DOOR_FRONT_RIGHT_POSITION": "door_front_right",
    "DOOR_REAR_LEFT_POSITION": "door_rear_left",
    "DOOR_REAR_RIGHT_POSITION": "door_rear_right",
    "DOOR_BOOT_POSITION": "door_boot",
    "DOOR_ENGINE_HOOD_POSITION": "door_engine_hood",
}
WINDOW_STATUS_KEYS: dict[str, str] = {
    "WINDOW_FRONT_LEFT_STATUS": "window_front_left",
    "WINDOW_FRONT_RIGHT_STATUS": "window_front_right",
    "WINDOW_REAR_LEFT_STATUS": "window_rear_left",
    "WINDOW_REAR_RIGHT_STATUS": "window_rear_right",
    "WINDOW_SUNROOF_STATUS": "window_sunroof",
}
LOCK_STATUS_KEYS: dict[str, str] = {
    "LOCK_FRONT_LEFT_STATUS": "lock_status_front_left",
    "LOCK_FRONT_RIGHT_STATUS": "lock_status_front_right",
    "LOCK_REAR_LEFT_STATUS": "lock_status_rear_left",
    "LOCK_REAR_RIGHT_STATUS": "lock_status_rear_right",
    "LOCK_BOOT_STATUS": "lock_status_boot",
}

# EV_IS_PLUGGED_IN values from subarulink/const.py that indicate the plug is in.
# Any other value (including UNPLUGGED / UNKNOWN / None) counts as not plugged in.
EV_PLUGGED_IN_STATES = frozenset({"CHARGING", "LOCKED_CONNECTED", "UNLOCKED_CONNECTED"})
API_KEY_EV_IS_PLUGGED_IN = "EV_IS_PLUGGED_IN"
API_KEY_EV_CHARGER_STATE_TYPE = "EV_CHARGER_STATE_TYPE"
EV_CHARGING_STATE = "CHARGING"

# vehicle_health response shape (see integration debug diagnostics)
HEALTH_ISTROUBLE = "ISTROUBLE"
HEALTH_FEATURES = "FEATURES"

# Subaru MIL (Malfunction Indicator Lamp) feature codes -> translation keys.
# Only codes the vehicle actually reports (via vehicle_features) get entities.
# b2cCode (Subaru's own API category label) disambiguates codes whose meaning
# isn't obvious from the featureCode alone, e.g. ATF_MIL's b2cCode is
# "oilTemp" — a temperature warning, not a fluid-level one.
MIL_TRANSLATION_KEYS: dict[str, str] = {
    # SRS = Supplemental Restraint System; b2cCode "airbag"
    "SRS_MIL": "mil_srs",
    # AWD = All-Wheel Drive; b2cCode "awd"
    "AWD_MIL": "mil_awd",
    # ABS = Anti-lock Braking System; b2cCode "abs"
    "ABS_MIL": "mil_abs",
    # ATF = Automatic Transmission Fluid; b2cCode "oilTemp" — temperature, not level
    "ATF_MIL": "mil_atf",
    # BSDRCT = Blind Spot Detection / Rear Cross Traffic; b2cCode "blindspot"
    "BSDRCT_MIL": "mil_bsdrct",
    # CEL = Check Engine Light; b2cCode "engineFail"
    "CEL_MIL": "mil_cel",
    # EBD = Electronic Brakeforce Distribution; b2cCode "ebd"
    "EBD_MIL": "mil_ebd",
    # EPB = Electric Parking Brake; b2cCode "pkgBrake"
    "EPB_MIL": "mil_epb",
    # EOL = Engine Oil Level; b2cCode "oilWarning"
    "EOL_MIL": "mil_eol",
    # ESS = EyeSight (driver assist) Safety System; b2cCode "eyesight"
    "ESS_MIL": "mil_ess",
    # ISS = Idle Stop & Start (auto start-stop); b2cCode "iss"
    "ISS_MIL": "mil_iss",
    # OPL = Oil Pressure Low; b2cCode "oilPres"
    "OPL_MIL": "mil_opl",
    # EPAS = Electric Power-Assisted Steering; b2cCode "epas"
    "EPAS_MIL": "mil_epas",
    # RAB = Reverse Automatic Braking; b2cCode "revBrake"
    "RAB_MIL": "mil_rab",
    # TEL = Telematics (Starlink); b2cCode "telematics"
    "TEL_MIL": "mil_tel",
    # TPMS = Tire Pressure Monitoring System; b2cCode "tpms"
    "TPMS_MIL": "mil_tpms",
    # VDC = Vehicle Dynamics Control (stability control); b2cCode "vdc"
    "VDC_MIL": "mil_vdc",
    # WASH = Washer fluid level; b2cCode "washer"
    "WASH_MIL": "mil_wash",
    # SRH = Steering Responsive Headlights; b2cCode "srh"
    "SRH_MIL": "mil_srh",
}

# Status values that mean a door/window is closed. The API has used both
# "CLOSED" (doors) and "CLOSE" (windows) historically.
OPENING_CLOSED_VALUES = frozenset({"CLOSED", "CLOSE"})
# Per-field sentinels meaning "no data", distinct from the whole-coordinator
# unavailable state. Compared case-insensitively since the API is inconsistent.
UNKNOWN_STATUSES = frozenset({"UNKNOWN", "UNAVAILABLE"})


@dataclass(frozen=True, kw_only=True)
class SubaruBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Subaru binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


def _vehicle_status_is_on(
    api_key: str,
    is_on: Callable[[str], bool],
) -> Callable[[dict[str, Any]], bool | None]:
    """Build an is_on getter for a single vehicle_status string field.

    The predicate is applied to the raw API value, uppercased (e.g. "CLOSED",
    "LOCKED", "UNLOCKED_CONNECTED") since the API is inconsistent about
    casing. Missing or unknown/unavailable values short-circuit to None so
    the entity reports as `unknown` rather than a false off/on.
    """

    def getter(vehicle_data: dict[str, Any]) -> bool | None:
        status = (vehicle_data.get(VEHICLE_STATUS) or {}).get(api_key)
        if status is None:
            return None
        status = status.upper()
        if status in UNKNOWN_STATUSES:
            return None
        return is_on(status)

    return getter


def _mil_is_on(feature: str) -> Callable[[dict[str, Any]], bool | None]:
    """Per-MIL getter from vehicle_health.FEATURES[<feature>].ISTROUBLE."""

    def getter(vehicle_data: dict[str, Any]) -> bool | None:
        features = (vehicle_data.get(VEHICLE_HEALTH) or {}).get(HEALTH_FEATURES) or {}
        feature_health = features.get(feature)
        if not feature_health or HEALTH_ISTROUBLE not in feature_health:
            return None
        return bool(feature_health[HEALTH_ISTROUBLE])

    return getter


def _overall_trouble_is_on(vehicle_data: dict[str, Any]) -> bool | None:
    """Overall vehicle_health.ISTROUBLE rollup."""
    health = vehicle_data.get(VEHICLE_HEALTH)
    if not health or HEALTH_ISTROUBLE not in health:
        return None
    return bool(health[HEALTH_ISTROUBLE])


# Predicates applied to the raw vehicle_status string for each entity group.
def _is_open(status: str) -> bool:
    """Door/window predicate — anything not in the closed set is open."""
    return status not in OPENING_CLOSED_VALUES


def _is_unlocked(status: str) -> bool:
    """Per-door lock predicate — anything other than LOCKED is unlocked."""
    return status != "LOCKED"


def _is_plugged_in(status: str) -> bool:
    """EV plug predicate — any documented connected state counts as plugged in."""
    return status in EV_PLUGGED_IN_STATES


def _is_charging(status: str) -> bool:
    """EV charging predicate — only CHARGING means actively charging."""
    return status == EV_CHARGING_STATE


# Static descriptions for entities that are created for every Gen2+ vehicle.
# MIL diagnostics are built dynamically below based on vehicle_features.
BINARY_SENSORS: tuple[SubaruBinarySensorEntityDescription, ...] = (
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.DOOR,
            is_on_fn=_vehicle_status_is_on(api_key, _is_open),
        )
        for api_key, trans_key in DOOR_POSITION_KEYS.items()
    ),
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.WINDOW,
            is_on_fn=_vehicle_status_is_on(api_key, _is_open),
        )
        for api_key, trans_key in WINDOW_STATUS_KEYS.items()
    ),
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.LOCK,
            is_on_fn=_vehicle_status_is_on(api_key, _is_unlocked),
        )
        for api_key, trans_key in LOCK_STATUS_KEYS.items()
    ),
)

OVERALL_HEALTH_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key="health_istrouble",
    translation_key="health_istrouble",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=_overall_trouble_is_on,
)

EV_PLUG_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key=API_KEY_EV_IS_PLUGGED_IN,
    translation_key="ev_is_plugged_in",
    device_class=BinarySensorDeviceClass.PLUG,
    is_on_fn=_vehicle_status_is_on(API_KEY_EV_IS_PLUGGED_IN, _is_plugged_in),
)

EV_CHARGING_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key=API_KEY_EV_CHARGER_STATE_TYPE,
    translation_key="is_charging",
    device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    entity_registry_enabled_default=False,
    is_on_fn=_vehicle_status_is_on(API_KEY_EV_CHARGER_STATE_TYPE, _is_charging),
)


def _build_mil_descriptions(
    features: list[str],
) -> list[SubaruBinarySensorEntityDescription]:
    """Return MIL descriptions for MIL feature codes that the vehicle reports."""
    return [
        SubaruBinarySensorEntityDescription(
            key=feature,
            translation_key=MIL_TRANSLATION_KEYS[feature],
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            # Per-MIL entities are disabled by default to avoid creating ~19
            # mostly-off entries per vehicle; the overall rollup stays enabled.
            entity_registry_enabled_default=False,
            is_on_fn=_mil_is_on(feature),
        )
        for feature in features
        if feature in MIL_TRANSLATION_KEYS
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SubaruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru binary sensors by config_entry."""
    coordinator = config_entry.runtime_data.coordinator
    vehicle_info = config_entry.runtime_data.vehicles

    entities: list[SubaruBinarySensor] = []
    for info in vehicle_info.values():
        # Doors/windows/locks/health are only reported on Gen2+ vehicles.
        if info[VEHICLE_API_GEN] not in GEN_2_AND_NEWER:
            continue
        descriptions: list[SubaruBinarySensorEntityDescription] = list(BINARY_SENSORS)
        descriptions.append(OVERALL_HEALTH_BINARY_SENSOR)
        if info[VEHICLE_HAS_EV]:
            descriptions.append(EV_PLUG_BINARY_SENSOR)
            descriptions.append(EV_CHARGING_BINARY_SENSOR)

        vehicle_data = (coordinator.data or {}).get(info[VEHICLE_VIN]) or {}
        features = vehicle_data.get(VEHICLE_FEATURES) or []
        descriptions.extend(_build_mil_descriptions(features))

        entities.extend(
            SubaruBinarySensor(info, coordinator, description)
            for description in descriptions
        )
    async_add_entities(entities)


class SubaruBinarySensor(SubaruCoordinatorEntity, BinarySensorEntity):
    """Representation of a Subaru binary sensor."""

    entity_description: SubaruBinarySensorEntityDescription

    def __init__(
        self,
        vehicle_info: dict[str, Any],
        coordinator: SubaruDataUpdateCoordinator,
        description: SubaruBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(vehicle_info, coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the sensor is on (open / unlocked / has trouble)."""
        return self.entity_description.is_on_fn(self.coordinator.data[self.vin])
