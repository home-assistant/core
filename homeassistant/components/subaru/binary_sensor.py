"""Support for Subaru binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
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

# Keys returned by subarulink controller.get_data() inside vehicle_status.
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

# EV_IS_PLUGGED_IN values meaning connected; other known values mean not
# connected.
EV_PLUGGED_IN_STATES = frozenset({"CHARGING", "LOCKED_CONNECTED", "UNLOCKED_CONNECTED"})
API_KEY_EV_IS_PLUGGED_IN = "EV_IS_PLUGGED_IN"
API_KEY_EV_CHARGER_STATE_TYPE = "EV_CHARGER_STATE_TYPE"
EV_CHARGING_STATE = "CHARGING"

# vehicle_health response shape (see integration debug diagnostics).
HEALTH_ISTROUBLE = "ISTROUBLE"
HEALTH_FEATURES = "FEATURES"

# Subaru MIL (Malfunction Indicator Lamp) feature codes -> translation keys.
# ATF_MIL is a transmission temperature warning, not fluid level.
MIL_TRANSLATION_KEYS: dict[str, str] = {
    "SRS_MIL": "mil_srs",
    "AWD_MIL": "mil_awd",
    "ABS_MIL": "mil_abs",
    "ATF_MIL": "mil_atf",
    "BSDRCT_MIL": "mil_bsdrct",
    "CEL_MIL": "mil_cel",
    "EBD_MIL": "mil_ebd",
    "EPB_MIL": "mil_epb",
    "EOL_MIL": "mil_eol",
    "ESS_MIL": "mil_ess",
    "ISS_MIL": "mil_iss",
    "OPL_MIL": "mil_opl",
    "EPAS_MIL": "mil_epas",
    "RAB_MIL": "mil_rab",
    "TEL_MIL": "mil_tel",
    "TPMS_MIL": "mil_tpms",
    "VDC_MIL": "mil_vdc",
    "WASH_MIL": "mil_wash",
    "SRH_MIL": "mil_srh",
}

# "CLOSED" (doors) or "CLOSE" (windows) means closed.
OPENING_CLOSED_VALUES = frozenset({"CLOSED", "CLOSE"})
# Sentinel values meaning "no data"; compared case-insensitively.
UNKNOWN_STATUSES = frozenset({"UNKNOWN", "UNAVAILABLE", "NOT_EQUIPPED"})


@dataclass(frozen=True, kw_only=True)
class SubaruBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Subaru binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


def _vehicle_status_value(vehicle_data: dict[str, Any], api_key: str) -> str | None:
    """Return the normalized vehicle_status value for api_key, or None if missing/unknown."""
    status = (vehicle_data.get(VEHICLE_STATUS) or {}).get(api_key)
    if status is None:
        return None
    status = status.upper()
    return None if status in UNKNOWN_STATUSES else status


def _opening_is_on(vehicle_data: dict[str, Any], api_key: str) -> bool | None:
    """Whether a door/window field is open."""
    value = _vehicle_status_value(vehicle_data, api_key)
    return None if value is None else value not in OPENING_CLOSED_VALUES


def _lock_is_on(vehicle_data: dict[str, Any], api_key: str) -> bool | None:
    """Whether a lock field is unlocked."""
    value = _vehicle_status_value(vehicle_data, api_key)
    return None if value is None else value != "LOCKED"


def _mil_trouble(vehicle_data: dict[str, Any], feature: str) -> bool | None:
    """Return vehicle_health.FEATURES[feature].ISTROUBLE, or None if not reported."""
    features = (vehicle_data.get(VEHICLE_HEALTH) or {}).get(HEALTH_FEATURES) or {}
    feature_health = features.get(feature)
    if not feature_health or HEALTH_ISTROUBLE not in feature_health:
        return None
    return bool(feature_health[HEALTH_ISTROUBLE])


# Static descriptions for entities that are created for every Gen2+ vehicle.
# MIL diagnostics are built dynamically below based on vehicle_features.
BINARY_SENSORS: tuple[SubaruBinarySensorEntityDescription, ...] = (
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.DOOR,
            is_on_fn=partial(_opening_is_on, api_key=api_key),
        )
        for api_key, trans_key in DOOR_POSITION_KEYS.items()
    ),
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.WINDOW,
            is_on_fn=partial(_opening_is_on, api_key=api_key),
        )
        for api_key, trans_key in WINDOW_STATUS_KEYS.items()
    ),
    *(
        SubaruBinarySensorEntityDescription(
            key=api_key,
            translation_key=trans_key,
            device_class=BinarySensorDeviceClass.LOCK,
            is_on_fn=partial(_lock_is_on, api_key=api_key),
        )
        for api_key, trans_key in LOCK_STATUS_KEYS.items()
    ),
)

OVERALL_HEALTH_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key="health_istrouble",
    translation_key="health_istrouble",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=lambda d: (
        None
        if not (health := d.get(VEHICLE_HEALTH)) or HEALTH_ISTROUBLE not in health
        else bool(health[HEALTH_ISTROUBLE])
    ),
)

EV_PLUG_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key=API_KEY_EV_IS_PLUGGED_IN,
    translation_key="ev_is_plugged_in",
    device_class=BinarySensorDeviceClass.PLUG,
    is_on_fn=lambda d: (
        None
        if (v := _vehicle_status_value(d, API_KEY_EV_IS_PLUGGED_IN)) is None
        else v in EV_PLUGGED_IN_STATES
    ),
)

EV_CHARGING_BINARY_SENSOR = SubaruBinarySensorEntityDescription(
    key=API_KEY_EV_CHARGER_STATE_TYPE,
    translation_key="is_charging",
    device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    entity_registry_enabled_default=False,
    is_on_fn=lambda d: (
        None
        if (v := _vehicle_status_value(d, API_KEY_EV_CHARGER_STATE_TYPE)) is None
        else v == EV_CHARGING_STATE
    ),
)


def _build_mil_descriptions(
    features: list[str],
) -> list[SubaruBinarySensorEntityDescription]:
    """Return MIL descriptions for MIL feature codes that the vehicle reports.

    Built once at setup; a MIL code that starts appearing later (partial
    first poll, or a code only reported once triggered) needs a reload.
    """
    return [
        SubaruBinarySensorEntityDescription(
            key=feature,
            translation_key=MIL_TRANSLATION_KEYS[feature],
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            # Disabled by default to avoid ~19 mostly-off entries per
            # vehicle; the overall health rollup stays enabled.
            entity_registry_enabled_default=False,
            is_on_fn=partial(_mil_trouble, feature=feature),
        )
        for feature in features
        if feature in MIL_TRANSLATION_KEYS
    ]


def _has_data(
    description: SubaruBinarySensorEntityDescription, vehicle_status: dict[str, Any]
) -> bool:
    """Whether a door/window/lock description should be created.

    Doors report even on an empty vehicle_status (a failed fetch), so
    they're excluded only when explicitly NOT_EQUIPPED. Windows/locks/EV
    fields are omitted entirely when unsupported, so presence decides.
    """
    if description.key in DOOR_POSITION_KEYS:
        return vehicle_status.get(description.key, "").upper() != "NOT_EQUIPPED"
    return description.key in vehicle_status


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
        vehicle_data = (coordinator.data or {}).get(info[VEHICLE_VIN]) or {}
        vehicle_status = vehicle_data.get(VEHICLE_STATUS) or {}

        descriptions: list[SubaruBinarySensorEntityDescription] = [
            description
            for description in BINARY_SENSORS
            if _has_data(description, vehicle_status)
        ]
        descriptions.append(OVERALL_HEALTH_BINARY_SENSOR)
        if info[VEHICLE_HAS_EV]:
            if EV_PLUG_BINARY_SENSOR.key in vehicle_status:
                descriptions.append(EV_PLUG_BINARY_SENSOR)
            if EV_CHARGING_BINARY_SENSOR.key in vehicle_status:
                descriptions.append(EV_CHARGING_BINARY_SENSOR)

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
