"""TFA.me station integration: sensor.py."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TFAmeConfigEntry, TFAmeUpdateCoordinator
from .helper import TFAmeBatteryState, TFAmeWindDirection, battery_state, wind_direction

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TFAmeSensorEntityDescription(SensorEntityDescription):
    """Entity description for TFA.me sensor entity."""

    value_fn: Callable[[TFAmeSensorEntity, dict[str, Any]], StateType] | None = None


TFA_ME_ENTITY_DESCRIPTIONS: dict[str, TFAmeSensorEntityDescription] = {
    "temperature": TFAmeSensorEntityDescription(
        key="temperature",
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
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # CO2 (Air quality)
    "co2": TFAmeSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Barometric pressure
    "barometric_pressure": TFAmeSensorEntityDescription(
        key="barometric_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # RSSI, 868 MHz signal strength, (not dB/dBm, value range: 0..255)
    "rssi": TFAmeSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity, data: int(data["value"]),
    ),
    # Low battery warning states: 0 = OK, 1 = low (warning), 2 = critical low (urgent warning)
    # 3 = battery missing/removed (Remark: some sensor have more than one power supply)
    "lowbatt": TFAmeSensorEntityDescription(
        key="lowbatt",
        translation_key="lowbatt",
        device_class=SensorDeviceClass.ENUM,
        options=list(TFAmeBatteryState),
        value_fn=lambda entity, data: battery_state(data["value"]),
    ),
    # Wind direction (Index 0..15 -> to string N, NNE, ...)
    "wind_direction": TFAmeSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.ENUM,
        options=list(TFAmeWindDirection),
        value_fn=lambda entity, data: wind_direction(data["value"]),
    ),
    # Wind direction in degrees: calculated from the 16-level index
    "wind_direction_deg": TFAmeSensorEntityDescription(
        key="wind_direction_deg",
        translation_key="wind_direction_deg",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Wind speed & gust
    "wind_speed": TFAmeSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    "wind_gust": TFAmeSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
    ),
    # Absolute rain gauge (since installation)
    "rain": TFAmeSensorEntityDescription(
        key="rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda entity, data: float(data["value"]),
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
                continue

            try:
                sensor_id = extract_sensor_id(unique_id)
                measure_name = unique_id.split("_", 2)[2]
            except ValueError, IndexError:
                continue

            description = TFA_ME_ENTITY_DESCRIPTIONS.get(measure_name)
            if description is None:
                continue

            new_entities.append(
                TFAmeSensorEntity(
                    coordinator,
                    sensor_id,
                    unique_id,
                    description,
                )
            )
            coordinator.sensor_entity_list.append(unique_id)

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()

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
        description: TFAmeSensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""

        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self.uid: str = unique_id
        self.entity_description = description

        # Do not set self.entity_id: HA will do and user can edit this entity ID later
        # Name schema created by HA with x... = Sensor ID, y... = Gateway/station ID:
        # tfa_me_xxx_xxx_xxx_yyyyyyyyy_MeasurementName, e.g. "tfa_me_a0f_fff_f81_05b3e4e44_humidity"
        self.gateway_id = self.coordinator.data.gateway_id
        self.sensor_id = sensor_id

        ids_str = f"{sensor_id}_{self.gateway_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ids_str)},
            name=self.format_string_tfa_id(self.sensor_id, self.gateway_id),
            manufacturer="TFA/Dostmann",
            model=self.coordinator.get_device_description(sensor_id),
        )

        # Depending on station or sensor add additional information
        hex_value = int(sensor_id[:2], 16)  # This is the device type
        if hex_value < 160:
            # Station: add URL to station main menu, SW version & serial
            self._attr_device_info["configuration_url"] = (
                f"http://{coordinator.host}/ha_menu"
            )
            self._attr_device_info["sw_version"] = self.coordinator.data.gateway_sw
            self._attr_device_info["serial_number"] = self.format_string_tfa_id_only(
                self.gateway_id
            )
        else:  # Sensor: add serial
            self._attr_device_info["serial_number"] = self.format_string_tfa_id_only(
                self.sensor_id
            )

    def format_string_tfa_id(self, serial: str, gateway_id: str) -> str:
        """Format a TFA.me serial number including the gateway ID."""
        return (
            f"TFA.me {serial[:3].upper()}-{serial[3:6].upper()}-"
            f"{serial[6:].upper()} ({gateway_id.upper()})"
        )

    def format_string_tfa_id_only(self, serial: str) -> str:
        """Format a TFA.me serial number."""
        return f"{serial[:3].upper()}-{serial[3:6].upper()}-{serial[6:].upper()}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the measurement value."""
        if (data := self.coordinator.data.entities.get(self.uid)) is None:
            return None

        last_update_ts = int(data["ts"])
        utc_now_ts = int(dt_util.utcnow().timestamp())
        timeout = self.coordinator.get_device_timeout(self.sensor_id)

        if (utc_now_ts - last_update_ts) > timeout:
            return None

        desc: TFAmeSensorEntityDescription = self.entity_description

        if desc.value_fn is not None:
            return desc.value_fn(self, data)

        # Generic fallback
        return data.get("value")

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measurement value,  e.g. for wind speed unit is "m/s"."""

        if (data := self.coordinator.data.entities.get(self.uid)) is None:
            return None
        return str(unit) if (unit := data["unit"]) else None

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.uid in self.coordinator.data.entities
