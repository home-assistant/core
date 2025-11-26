"""TFA.me station integration: sensor.py."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from tfa_me_ha_local.history import SensorHistory

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_MAPPING,
    DOMAIN,
    MEASUREMENT_TO_TRANSLATION_KEY,
    TIMEOUT_MAPPING,
)
from .coordinator import TFAmeConfigEntry, TFAmeDataCoordinator

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TFAmeSensorEntityDescription(SensorEntityDescription):
    """Entity description for TFA.me sensor entity."""

    # value_fn gets entity and th raw data dict (coordinator.data[self.uid])
    value_fn: Callable[["TFAmeSensorEntity", dict[str, Any]], StateType] | None = None


def _calc_rain_last_hour(entity: "TFAmeSensorEntity", data: dict[str, Any]) -> float:
    """Get rainfall of the last hour and optional handle a reset."""
    reset_rain = data.get("reset_rain", False)
    if reset_rain:
        entity.rain_history.clear()
        entity.coordinator.data[entity.uid]["reset_rain"] = False

    value = entity.rain_history.get_rain_amount()
    return round(value, 1)


def _calc_rain_last_24h(entity: "TFAmeSensorEntity", data: dict[str, Any]) -> float:
    """Get rainfall of the last 24 hours and optional handle a reset."""
    reset_rain = data.get("reset_rain", False)
    if reset_rain:
        entity.rain_history_24.clear()
        entity.coordinator.data[entity.uid]["reset_rain"] = False

    value = entity.rain_history_24.get_rain_amount()
    return round(value, 1)


# All TFA.me entity descriptions
TFA_ME_ENTITY_DESCRIPTIONS: dict[str, TFAmeSensorEntityDescription] = {
    # Temperature & temperature probe
    "temperature": TFAmeSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    "temperature_probe": TFAmeSensorEntityDescription(
        key="temperature_probe",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Relative humidity
    "humidity": TFAmeSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # CO2 (Air quality)
    "co2": TFAmeSensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Barometric pressure
    "barometric_pressure": TFAmeSensorEntityDescription(
        key="barometric_pressure",
        translation_key="barometric_pressure",
        device_class=SensorDeviceClass.PRESSURE,  # or ATMOSPHERIC_PRESSURE ?
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # RSSI, 868 MHz signal strength, (not dB/dBm, value range: 0..255)
    "rssi": TFAmeSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Low battery warning: 0 = OK, 1 = low (warning)
    "lowbatt": TFAmeSensorEntityDescription(
        key="lowbatt",
        translation_key="lowbatt",
        state_class=None,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Wind direction (Index 0..15)
    "wind_direction": TFAmeSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Wind direction in degrees: calculated from the 16-level index
    "wind_direction_deg": TFAmeSensorEntityDescription(
        key="wind_direction_deg",
        translation_key="wind_direction",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity, data: round(
            float(entity.coordinator.data[entity.uid.replace("_deg", "")]["value"])
            * (360.0 / 16.0),
            1,
        ),
    ),
    # Wind speed & gust
    "wind_speed": TFAmeSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: round(float(data["value"]), 1),
    ),
    "wind_gust": TFAmeSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: round(float(data["value"]), 1),
    ),
    # Absolute rain gauge (since installation)
    "rain": TFAmeSensorEntityDescription(
        key="rain",
        translation_key="rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Relative rainfall (since last reset / HA start)
    "rain_relative": TFAmeSensorEntityDescription(
        key="rain_relative",
        translation_key="rain_relative",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: round(
            float(data["value"]) - float(entity.init_measure_value),
            1,
        ),
    ),
    # Rain last hour (rolling window), based on entity.rain_history
    "rain_1_hour": TFAmeSensorEntityDescription(
        key="rain_1_hour",
        translation_key="rain_1_hour",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_calc_rain_last_hour,
    ),
    # Rainfall in the last 24 hours (rolling window), based on entity.rain_history_24
    "rain_24_hours": TFAmeSensorEntityDescription(
        key="rain_24_hours",
        translation_key="rain_24_hours",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_calc_rain_last_24h,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TFAmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TFA.me as Sensor."""

    # Get coordinator
    coordinator = hass.data.setdefault(DOMAIN, {})[entry.entry_id]
    # Initialize first refresh/request and wait for parsed JSON data from coordinator
    sensors_start = []
    for unique_id in coordinator.data:
        sensor_id = coordinator.data[unique_id]["sensor_id"]
        if unique_id not in coordinator.sensor_entity_list:
            sensors_start.append(TFAmeSensorEntity(coordinator, sensor_id, unique_id))
            coordinator.sensor_entity_list.append(unique_id)

    # Add all entities
    async_add_entities(sensors_start, True)


class TFAmeSensorEntity(CoordinatorEntity, SensorEntity):
    """TFA.me sensor entity, represents in HA a single measurement value of a sensor."""

    # Narrow the type of entity_description for this entity class
    entity_description: TFAmeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TFAmeDataCoordinator,
        sensor_id: str,
        entity_id: str,
    ) -> None:
        """Initialize sensor entity."""
        try:
            super().__init__(coordinator)
            self._initialized_once = False
            self.coordinator = coordinator
            self._attr_unique_id = (
                entity_id  # Unique ID (sets unique_id), will never be changed
            )
            self.host = coordinator.host
            self.name_with_station_id = coordinator.name_with_station_id
            self.entity_id = entity_id  # User can edit this entity ID
            self.uid: str = entity_id
            self.gateway_id = self.coordinator.data[self.uid]["gateway_id"]

            self.sensor_id = sensor_id
            label = (
                f"via {self.gateway_id}" if getattr(self, "gateway_id", None) else "via"
            )
            self._attr_labels: list[str] = [label]
            self._attr_icon = ""
            ids_str = f"{sensor_id}_{self.gateway_id}"
            self._attr_device_info = {
                "identifiers": {
                    (
                        DOMAIN,
                        ids_str,
                    )  # Entities for sensors
                },  # Unique ID for device/sensor
                "name": self.format_string_tfa_id(
                    self.sensor_id, self.gateway_id, self.name_with_station_id
                ),  # 'TFA.me XXX-XXX-XXX'
                "manufacturer": "TFA/Dostmann",
                "model": self.format_string_tfa_type(
                    sensor_id
                ),  # 'Sensor/Station type XX'
            }

            self.measure_name = self.coordinator.data[self.uid]["measurement"]
            # Some rain specials
            if self.measure_name == "rain_1_hour":
                self.rain_history = SensorHistory(max_age_minutes=60)

            if self.measure_name == "rain_24_hours":
                self.rain_history_24 = SensorHistory(max_age_minutes=24 * 60)

            # If this is a station add URL to station
            hex_value = int(sensor_id[:2], 16)
            if hex_value < 160:
                self._attr_device_info["configuration_url"] = (
                    f"http://{coordinator.host}/ha_menu"
                )

            # Add icon for measurement
            self.init_measure_value: float = 0
            self.measure_name = self.coordinator.data[self.uid]["measurement"]
            self.init_measure_value = self.coordinator.data[self.uid]["value"]

            description = TFA_ME_ENTITY_DESCRIPTIONS.get(self.measure_name)
            if description is not None:
                self.entity_description = description
                # Set icon translations for entity, MDI icon: https://pictogrammers.com/library/mdi/
                self._attr_translation_key = description.translation_key
                # state_class/device_class/ come from entity_description
            else:
                # Fallback for unknown measurements
                self._attr_translation_key = None

        except (ValueError, TypeError, KeyError):
            return

    def _get_translation_key(self, measurement: str | None) -> str | None:
        """Map measurement type to translation key for icon translations."""
        if measurement is None:
            return None
        return MEASUREMENT_TO_TRANSLATION_KEY.get(measurement, measurement)

    async def async_added_to_hass(self) -> None:
        """Called once if entity is added to HA instance."""
        await super().async_added_to_hass()
        self._initialized_once = True

        if self.name_with_station_id:
            ent_reg = er.async_get(self.hass)
            reg_entry = ent_reg.async_get(self.entity_id)
            if not reg_entry:
                return

            # Set a label if not available in registry
            if not reg_entry.labels:
                # User labels are not overwritten
                if self.entity_id:
                    ent_reg.async_update_entity(
                        self.entity_id, labels=set(self._attr_labels)
                    )

    def _handle_coordinator_update(self) -> None:
        """Called when coordinator has new data, used to update rain histories."""

        if "rain_hour" in self.uid:
            try:
                value = float(self.coordinator.data[self.uid]["value"])
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        if "rain_24hours" in self.uid:
            try:
                value = float(self.coordinator.data[self.uid]["value"])
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history_24.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        # Update state in HA
        super()._handle_coordinator_update()

    def format_string_tfa_id(self, s: str, gw_id: str, name_with_station_id: bool):
        """String helper for sensor names, convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        if name_with_station_id:
            return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()} ({gw_id.upper()})"

        return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}"

    def format_string_tfa_type(self, s: str):
        """String helper for sensor/station types, convert serial string 'xxxxxxxxx' into 'Sensor/station type XX'."""

        type_id: str = (s[:2]).upper()
        info_str: str = "?"
        try:
            info_str = DEVICE_MAPPING[type_id]
        except KeyError:
            info_str = "?"
        return info_str

    @property
    def measurement_name(self):
        """Name of measurement, e.g. 'temperature', 'humidity'."""
        try:
            measurement_name = self.coordinator.data[self.uid]["measurement"]
        except (ValueError, TypeError, KeyError):
            return None

        return measurement_name

    @property
    def native_value(self) -> StateType:
        """Actual measurement value of an entity."""
        try:
            last_update_ts: int = int(self.coordinator.data[self.uid]["ts"])
            utc_now_ts = int(datetime.now().timestamp())
            timeout = self.get_timeout(self.sensor_id)
            if (utc_now_ts - last_update_ts) > timeout:
                return None

            data = self.coordinator.data[self.uid]
            desc: TFAmeSensorEntityDescription = self.entity_description

            if desc.value_fn is not None:
                return desc.value_fn(self, data)

            # generic fallback
            return data.get("value")

        except (ValueError, TypeError, KeyError):
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measurement value,  e.g. for wind speed unit is "m/s"."""

        try:
            unit = self.coordinator.data[self.uid]["unit"]
            if unit is None:
                return None  # HA shows "unavailable"
            return str(unit)
        except (ValueError, TypeError, KeyError):
            return ""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes dictionary for an entity: sensor_name, measurement, timestamp, icon."""

        try:
            sensor_data = self.coordinator.data[self.uid]
            return {
                "sensor_name": sensor_data["sensor_name"],
                "measurement": sensor_data["measurement"],
                "timestamp": sensor_data["timestamp"],
                "icon": self._attr_icon,
                "Via TFA.me station": self.gateway_id.upper(),
            }
        except (ValueError, TypeError, KeyError):
            return {}

    def get_timeout(self, sensor_id: str):
        """Return the timeout time for a station or sensor."""

        try:
            timeout_val = TIMEOUT_MAPPING[sensor_id[:2].upper()]
        except KeyError:
            timeout_val = 0
        return timeout_val

    async def async_update(self) -> None:
        """Manual Updating."""
        await self.coordinator.async_request_refresh()
