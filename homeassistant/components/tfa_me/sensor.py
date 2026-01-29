"""TFA.me station integration: sensor.py."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, cast

from tfa_me_ha_local.history import SensorHistory

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_MAPPING,
    DOMAIN,
    MEASUREMENT_TO_TRANSLATION_KEY,
    TIMEOUT_MAPPING,
)
from .coordinator import TFAmeConfigEntry, TFAmeDataCoordinator, resolve_tfa_host

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TFAmeSensorEntityDescription(SensorEntityDescription):
    """Entity description for TFA.me sensor entity."""

    # value_fn gets entity and the raw data dict (coordinator.data[self.uid])
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
    # Temperature
    "temperature": TFAmeSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Temperature probe
    "temperature_probe": TFAmeSensorEntityDescription(
        key="temperature_probe",
        translation_key="temperature_probe",
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
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
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
    # Low battery warning states: 0 = OK, 1 = low (warning), 2 = critical low (urgent warning)
    # 3 = battery missing/removed (Remark: some sensor have more then one power supply)
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
        suggested_display_precision=1,
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
    "rain_rel": TFAmeSensorEntityDescription(
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
    coordinator = entry.runtime_data
    # Initialize first refresh/request and wait for parsed JSON data from coordinator
    sensors_start = []
    for unique_id in coordinator.data:
        sensor_id = unique_id[17:26]  # sensor ID
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
        unique_id: str,
    ) -> None:
        """Initialize sensor entity."""
        try:
            super().__init__(coordinator)
            self._initialized_once = False
            self.coordinator = coordinator
            self._attr_unique_id = unique_id  # Unique ID (sets unique_id), will never be changed, name schema "StationID_SensorID_MeasurementValue"
            self.host = coordinator.host
            self.name_with_station_id = coordinator.name_with_station_id
            self.entity_id = unique_id  # User can edit this entity ID
            self.uid: str = unique_id
            self.gateway_id = self.coordinator.gateway_id
            self.sensor_id = sensor_id
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

            self.measure_name = self.uid[27:]
            # Some rain specials
            if self.measure_name == "rain_1_hour":
                self.rain_history = SensorHistory(max_age_minutes=60)

            if self.measure_name == "rain_24_hours":
                self.rain_history_24 = SensorHistory(max_age_minutes=24 * 60)

            # Depending on station or sensor add additional information
            hex_value = int(sensor_id[:2], 16)  # This is the device type
            if hex_value < 160:
                # Station: add URL to station main menu, SW version & serial
                host_resolved = resolve_tfa_host(coordinator.host)
                self._attr_device_info["configuration_url"] = (
                    f"http://{host_resolved}/ha_menu"
                )
                self._attr_device_info["sw_version"] = self.coordinator.gateway_sw
                self._attr_device_info["serial_number"] = (
                    self.format_string_tfa_id_only(self.gateway_id)
                )
            else:  # Sensor: add serial
                self._attr_device_info["serial_number"] = (
                    self.format_string_tfa_id_only(self.sensor_id)
                )

            # Add init value & description
            self.init_measure_value: float = 0
            self.init_measure_value = self.coordinator.data[self.uid]["value"]
            self.entity_description = cast(
                TFAmeSensorEntityDescription,
                TFA_ME_ENTITY_DESCRIPTIONS.get(self.measure_name),
            )

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

    def _handle_coordinator_update(self) -> None:
        """Called when coordinator has new data, used to update rain histories."""

        if "rain_1_hour" in self.uid:
            try:
                value = float(self.coordinator.data[self.uid]["value"])
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        if "rain_24_hours" in self.uid:
            try:
                value = float(self.coordinator.data[self.uid]["value"])
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history_24.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        # Update state in HA
        super()._handle_coordinator_update()

    def format_string_tfa_id(self, s: str, gw_id: str, name_with_station_id: bool):
        """String helper for station & sensor names, convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        if name_with_station_id:
            return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()} ({gw_id.upper()})"

        return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}"

    def format_string_tfa_id_only(self, s: str):
        """String helper for station & sensor names, convert string 'xxxxxxxxx' into 'XXX-XXX-XXX'."""
        return f"{s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}"

    def format_string_tfa_type(self, s: str):
        """String helper for sensor & station types, convert serial string 'xxxxxxxxx' into 'Sensor/Station type XX'."""

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
            measurement_name = self.uid[27:]  # measurement type
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
        """Extra attributes dictionary for an entity: sensor ID, measurement, timestamp, icon."""

        try:
            sensor_data = self.coordinator.data[self.uid]
            dt = datetime.fromtimestamp(
                int(sensor_data["ts"]), tz=UTC
            )  # ISO-8601-UTC format

            return {
                "Unique ID": self.format_string_tfa_id_only(self.uid[17:26].upper()),
                "Measurement": self.uid[27:],  # measurement type
                "Timestamp": dt,
                "icon": self._attr_icon,
                "Via TFA.me station": self.format_string_tfa_id_only(
                    self.gateway_id.upper()
                ),
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
