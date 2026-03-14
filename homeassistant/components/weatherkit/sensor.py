"""WeatherKit sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolumetricFlux
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_CURRENT_WEATHER, ATTR_WEATHER_ALERTS, DOMAIN
from .coordinator import WeatherKitDataUpdateCoordinator
from .entity import WeatherKitEntity

SENSORS = (
    SensorEntityDescription(
        key="precipitationIntensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="pressureTrend",
        device_class=SensorDeviceClass.ENUM,
        options=["rising", "falling", "steady"],
        translation_key="pressure_trend",
    ),
)

ALERT_SENSOR = SensorEntityDescription(
    key="weatherAlerts",
    translation_key="weather_alerts",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensor entities from a config_entry."""
    coordinator: WeatherKitDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[WeatherKitSensor | WeatherKitAlertSensor] = [
        WeatherKitSensor(coordinator, description) for description in SENSORS
    ]

    if ATTR_WEATHER_ALERTS in (coordinator.supported_data_sets or []):
        entities.append(WeatherKitAlertSensor(coordinator))

    async_add_entities(entities)


class WeatherKitSensor(
    CoordinatorEntity[WeatherKitDataUpdateCoordinator], WeatherKitEntity, SensorEntity
):
    """WeatherKit sensor entity."""

    def __init__(
        self,
        coordinator: WeatherKitDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        WeatherKitEntity.__init__(
            self, coordinator, unique_id_suffix=entity_description.key
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return native value from coordinator current weather."""
        return self.coordinator.data[ATTR_CURRENT_WEATHER][self.entity_description.key]


class WeatherKitAlertSensor(
    CoordinatorEntity[WeatherKitDataUpdateCoordinator], WeatherKitEntity, SensorEntity
):
    """WeatherKit sensor for weather alerts."""

    entity_description = ALERT_SENSOR

    def __init__(
        self,
        coordinator: WeatherKitDataUpdateCoordinator,
    ) -> None:
        """Initialize the alert sensor."""
        super().__init__(coordinator)
        WeatherKitEntity.__init__(self, coordinator, unique_id_suffix=ALERT_SENSOR.key)

    @property
    def _alerts(self) -> list[dict[str, Any]]:
        """Return the current list of alerts."""
        alerts_data = self.coordinator.data.get(ATTR_WEATHER_ALERTS)
        if alerts_data is None:
            return []
        return alerts_data.get("alerts", [])

    @property
    def native_value(self) -> int:
        """Return the number of active alerts."""
        return len(self._alerts)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details of each alert as extra state attributes."""
        alerts = self._alerts
        if not alerts:
            return None

        attrs: dict[str, Any] = {}
        for index, alert in enumerate(alerts, start=1):
            attrs[f"alert_{index}"] = alert.get("name")
            attrs[f"alert_severity_{index}"] = alert.get("severity")
            attrs[f"alert_source_{index}"] = alert.get("source")
            attrs[f"alert_time_{index}"] = alert.get("effectiveTime")
            attrs[f"alert_expiry_{index}"] = alert.get("expireTime")

        return attrs
