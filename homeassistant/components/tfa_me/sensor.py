"""TFA.me station integration: sensor.py."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tfa_me_ha_local.history import SensorHistory

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEVICE_MAPPING, DOMAIN, TIMEOUT_MAPPING
from .coordinator import TFAmeConfigEntry, TFAmeUpdateCoordinator, resolve_tfa_host

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TFAmeSensorEntityDescription(SensorEntityDescription):
    """Entity description for TFA.me sensor entity."""

    # value_fn gets entity and the raw data dict (coordinator.data.entities[self.uid])
    value_fn: Callable[[TFAmeSensorEntity, dict[str, Any]], StateType] | None = None


def _calc_rain_last_hour(entity: TFAmeSensorEntity, data: dict[str, Any]) -> float:
    """Get rainfall of the last hour and optional handle a reset."""
    return round(entity.rain_history.get_rain_amount(), 1)


def _calc_rain_last_24h(entity: TFAmeSensorEntity, data: dict[str, Any]) -> float:
    """Get rainfall of the last 24 hours and optional handle a reset."""
    return round(entity.rain_history_24.get_rain_amount(), 1)


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
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Low battery warning states: 0 = OK, 1 = low (warning), 2 = critical low (urgent warning)
    # 3 = battery missing/removed (Remark: some sensor have more than one power supply)
    "lowbatt": TFAmeSensorEntityDescription(
        key="lowbatt",
        translation_key="lowbatt",
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Wind direction (Index 0..15)
    "wind_direction": TFAmeSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Wind direction in degrees: calculated from the 16-level index
    "wind_direction_deg": TFAmeSensorEntityDescription(
        key="wind_direction_deg",
        translation_key="wind_direction_deg",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: round(
            float(
                entity.coordinator.data.entities[entity.uid.replace("_deg", "")][
                    "value"
                ]
            )
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


def extract_sensor_id(unique_id: str) -> str:
    """Parse TFA.me library unique ID to get sensor ID."""
    raw_id = unique_id.removeprefix("sensor.")
    _, sensor_id, _ = raw_id.split("_", 2)
    return sensor_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TFAmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TFA.me as Sensor."""
    coordinator = entry.runtime_data

    @callback
    def async_add_new_entities() -> None:
        """Add new sensor entities from coordinator data."""
        if coordinator.data is None:
            return

        new_entities: list[TFAmeSensorEntity] = []

        for unique_id in coordinator.data.entities:
            if unique_id in coordinator.sensor_entity_list:
                # Skipping known TFA.me unique ID
                continue

            try:
                sensor_id = extract_sensor_id(unique_id)
            except ValueError:
                # Skipping invalid TFA.me unique ID
                continue

            new_entities.append(
                TFAmeSensorEntity(
                    coordinator,
                    sensor_id,
                    unique_id,
                )
            )
            coordinator.sensor_entity_list.append(unique_id)

        if new_entities:
            async_add_entities(new_entities)

    # At HA start add known entities
    async_add_new_entities()

    # With every coordinator update search for new sensors
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class TFAmeSensorEntity(CoordinatorEntity[TFAmeUpdateCoordinator], SensorEntity):
    """TFA.me sensor entity, represents in HA a single measurement value of a sensor."""

    # Narrow the type of entity_description for this entity class
    entity_description: TFAmeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TFAmeUpdateCoordinator,
        sensor_id: str,
        unique_id: str,
    ) -> None:
        """Initialize sensor entity."""

        super().__init__(coordinator)

        # Unique ID (sets unique_id), will never be changed
        # Name schema for unique_id is: f"sensor.{StationID}_{SensorID}_{MeasurementName}".lower()
        self._attr_unique_id = unique_id.removeprefix("sensor.")
        self.uid: str = unique_id

        # Do not set self.entity_id: HA will do and user can edit this entity ID later
        # Name schema created by HA with x... = Sensor ID, y... = Gateway/station ID:
        # sensor.tfa_me_xxx_xxx_xxx_yyyyyyyyy_MeasurementName, e.g. "sensor.tfa_me_a0f_fff_f81_05b3e4e44_humidity"
        self.gateway_id = self.coordinator.data.gateway_id
        self.sensor_id = sensor_id

        try:
            ids_str = f"{sensor_id}_{self.gateway_id}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, ids_str)},
                name=self.format_string_tfa_id(self.sensor_id, self.gateway_id),
                manufacturer="TFA/Dostmann",
                model=self.format_string_tfa_type(sensor_id),
            )

            self.measure_name = self.uid.removeprefix("sensor.").split("_", 2)[2]

            # Some rain specials
            if self.measure_name == "rain_1_hour":
                self.rain_history = SensorHistory(max_age_minutes=60)
                self._add_rain_measurement()
            if self.measure_name == "rain_24_hours":
                self.rain_history_24 = SensorHistory(max_age_minutes=24 * 60)
                self._add_rain_measurement()

            # Depending on station or sensor add additional information
            hex_value = int(sensor_id[:2], 16)  # This is the device type
            if hex_value < 160:
                # Station: add URL to station main menu, SW version & serial
                host_resolved = resolve_tfa_host(coordinator.host)
                self._attr_device_info["configuration_url"] = (
                    f"http://{host_resolved}/ha_menu"
                )
                self._attr_device_info["sw_version"] = self.coordinator.data.gateway_sw
                self._attr_device_info["serial_number"] = (
                    self.format_string_tfa_id_only(self.gateway_id)
                )
            else:  # Sensor: add serial
                self._attr_device_info["serial_number"] = (
                    self.format_string_tfa_id_only(self.sensor_id)
                )

            # Add init value & description
            self.init_measure_value: str = self.coordinator.data.entities[self.uid][
                "value"
            ]
            self.entity_description = self._get_entity_description(self.measure_name)

        except (ValueError, TypeError, KeyError, IndexError) as err:
            raise ValueError("entity_error") from err

    def _get_entity_description(
        self, measure_name: str
    ) -> TFAmeSensorEntityDescription:
        """Return entity description for measurement."""

        description = TFA_ME_ENTITY_DESCRIPTIONS.get(measure_name)
        if description is None:
            raise ValueError(f"Unsupported TFA.me measurement: {measure_name}")

        return description

    def _add_rain_measurement(self) -> None:
        """Add current rain measurement to history."""
        try:
            value = float(self.coordinator.data.entities[self.uid]["value"])
            ts = self.coordinator.data.entities[self.uid]["ts"]
        except ValueError, TypeError, KeyError:
            return

        if "rain_1_hour" in self.uid:
            self.rain_history.add_measurement(value, ts)

        if "rain_24_hours" in self.uid:
            self.rain_history_24.add_measurement(value, ts)

    def _handle_coordinator_update(self) -> None:
        """Called when coordinator has new data, used to update rain histories, also optional reset rain."""

        data = self.coordinator.data.entities.get(self.uid)
        if data is not None and data.get("reset_rain", False):
            if "rain_1_hour" in self.uid:
                self.rain_history.clear()
            if "rain_24_hours" in self.uid:
                self.rain_history_24.clear()
            data["reset_rain"] = False

        self._add_rain_measurement()
        # Update state in HA
        super()._handle_coordinator_update()

    def format_string_tfa_id(self, s: str, gw_id: str):
        """String helper for station & sensor names, convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        return (
            f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()} ({gw_id.upper()})"
        )

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
    def native_value(self) -> StateType:
        """Actual measurement value of an entity."""
        try:
            last_update_ts: int = int(self.coordinator.data.entities[self.uid]["ts"])
            utc_now_ts = int(dt_util.utcnow().timestamp())
            timeout = self.get_timeout(self.sensor_id)
            if (utc_now_ts - last_update_ts) > timeout:
                return None

            data = self.coordinator.data.entities[self.uid]
            desc: TFAmeSensorEntityDescription = self.entity_description

            if desc.value_fn is not None:
                return desc.value_fn(self, data)

            # generic fallback
            return data.get("value")

        except ValueError, TypeError, KeyError:
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measurement value,  e.g. for wind speed unit is "m/s"."""

        try:
            unit = self.coordinator.data.entities[self.uid]["unit"]
            if unit is None:
                return None  # HA shows "unavailable"
            return str(unit)
        except ValueError, TypeError, KeyError:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for the entity."""
        try:
            sensor_data = self.coordinator.data.entities[self.uid]
            timestamp = int(sensor_data["ts"])
            measurement_timestamp = datetime.fromtimestamp(timestamp, tz=UTC)
        except ValueError, TypeError, KeyError:
            return {}

        return {
            "measurement_timestamp": measurement_timestamp,
        }

    def get_timeout(self, sensor_id: str):
        """Return the timeout time for a station or sensor."""

        try:
            timeout_val = TIMEOUT_MAPPING[sensor_id[:2].upper()]
        except KeyError:
            timeout_val = 0
        return timeout_val
