"""Support for the Environment Canada weather service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from env_canada import ECWeather
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_LOCATION,
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_STATION
from .coordinator import ECConfigEntry, ECDataUpdateCoordinator, ECSensorDataType


@dataclass(frozen=True, kw_only=True)
class ECSensorEntityDescription(SensorEntityDescription):
    """Describes Environment Canada sensor entity."""

    value_fn: Callable[[Any], Any]
    transform: Callable[[Any], Any] | None = None


SENSOR_TYPES: tuple[ECSensorEntityDescription, ...] = (
    ECSensorEntityDescription(
        key="condition",
        translation_key="condition",
        value_fn=lambda data: data.conditions.get("condition", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("dewpoint", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="high_temp",
        translation_key="high_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("high_temp", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="humidex",
        translation_key="humidex",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("humidex", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("humidity", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="icon_code",
        translation_key="icon_code",
        name="Icon code",
        value_fn=lambda data: data.conditions.get("icon_code", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="low_temp",
        translation_key="low_temp",
        name="Low temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("low_temp", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="normal_high",
        translation_key="normal_high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.conditions.get("normal_high", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="normal_low",
        translation_key="normal_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.conditions.get("normal_low", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="pop",
        translation_key="pop",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.conditions.get("pop", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("pressure", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("temperature", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="tendency",
        translation_key="tendency",
        value_fn=lambda data: data.conditions.get("tendency", {}).get("value"),
        transform=lambda val: str(val).capitalize(),
    ),
    ECSensorEntityDescription(
        key="text_summary",
        translation_key="text_summary",
        value_fn=lambda data: data.conditions.get("text_summary", {}).get("value"),
        transform=lambda val: val[:255],
    ),
    ECSensorEntityDescription(
        key="timestamp",
        translation_key="timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.metadata.timestamp,
    ),
    ECSensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("uv_index", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("visibility", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="wind_bearing",
        translation_key="wind_bearing",
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: data.conditions.get("wind_bearing", {}).get("value"),
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    ECSensorEntityDescription(
        key="wind_chill",
        translation_key="wind_chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("wind_chill", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="wind_dir",
        translation_key="wind_dir",
        value_fn=lambda data: data.conditions.get("wind_dir", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("wind_gust", {}).get("value"),
    ),
    ECSensorEntityDescription(
        key="wind_speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.conditions.get("wind_speed", {}).get("value"),
    ),
)


def _get_aqhi_value(data):
    if (aqhi := data.current) is not None:
        return aqhi
    if data.forecasts and (hourly := data.forecasts.get("hourly")) is not None:
        if values := list(hourly.values()):
            return values[0]
    return None


AQHI_SENSOR = ECSensorEntityDescription(
    key="aqhi",
    translation_key="aqhi",
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_get_aqhi_value,
)

ALERT_TYPES: dict[str, str] = {
    "advisories": "advisory",
    "endings": "ending",
    "statements": "statement",
    "warnings": "warning",
    "watches": "watch",
}


def _get_all_alerts(data: ECWeather) -> list[dict[str, Any]]:
    """Collect all alerts from all alert types into a flat list."""
    all_alerts: list[dict[str, Any]] = []
    for key, alert_type in ALERT_TYPES.items():
        all_alerts.extend(
            {**alert, "type": alert_type}
            for alert in data.alerts.get(key, {}).get("value") or []
        )
    return all_alerts


ALERTS_SENSOR = ECSensorEntityDescription(
    key="alerts",
    translation_key="alerts",
    value_fn=lambda data: len(_get_all_alerts(data)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ECConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    weather_coordinator = config_entry.runtime_data.weather_coordinator
    sensors: list[ECBaseSensorEntity] = [
        ECSensorEntity(weather_coordinator, desc) for desc in SENSOR_TYPES
    ]
    sensors.append(ECAlertSensorEntity(weather_coordinator, ALERTS_SENSOR))

    sensors.append(
        ECSensorEntity(config_entry.runtime_data.aqhi_coordinator, AQHI_SENSOR)
    )
    async_add_entities(sensors)


class ECBaseSensorEntity[DataT: ECSensorDataType](
    CoordinatorEntity[ECDataUpdateCoordinator[DataT]], SensorEntity
):
    """Environment Canada sensor base."""

    entity_description: ECSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ECDataUpdateCoordinator[DataT],
        description: ECSensorEntityDescription,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._ec_data = coordinator.ec_data
        self._attr_attribution = self._ec_data.metadata.attribution
        self._attr_unique_id = f"{coordinator.config_entry.title}-{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        value = self.entity_description.value_fn(self._ec_data)
        if value is not None and self.entity_description.transform:
            value = self.entity_description.transform(value)
        return value


class ECSensorEntity[DataT: ECSensorDataType](ECBaseSensorEntity[DataT]):
    """Environment Canada sensor for conditions."""

    def __init__(
        self,
        coordinator: ECDataUpdateCoordinator[DataT],
        description: ECSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._attr_extra_state_attributes = {
            ATTR_LOCATION: self._ec_data.metadata.location,
            ATTR_STATION: self._ec_data.metadata.station,
        }


class ECAlertSensorEntity(ECBaseSensorEntity[ECWeather]):
    """Environment Canada sensor for alerts."""

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        all_alerts = _get_all_alerts(self._ec_data)
        if not all_alerts:
            return None

        alerts: list[dict[str, Any]] = []
        for alert in all_alerts:
            alert_attrs: dict[str, Any] = {
                "title": alert.get("title"),
                "issued": alert.get("date"),
                "color": alert.get("alertColourLevel"),
                "expiry": alert.get("expiryTime"),
                "url": alert.get("url"),
                "text": alert.get("text"),
                "area": alert.get("area"),
                "status": alert.get("status"),
                "confidence": alert.get("confidence"),
                "impact": alert.get("impact"),
                "alert_code": alert.get("alert_code"),
                "type": alert.get("type"),
            }
            alerts.append({k: v for k, v in alert_attrs.items() if v is not None})

        return {
            ATTR_LOCATION: self._ec_data.metadata.location,
            ATTR_STATION: self._ec_data.metadata.station,
            "alerts": alerts,
        }
