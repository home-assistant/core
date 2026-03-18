"""Support for Notion sensors."""

from dataclasses import dataclass

from aionotion.listener.models import ListenerKind

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SENSOR_MOLD, SENSOR_TEMPERATURE
from .coordinator import NotionDataUpdateCoordinator
from .entity import NotionEntity, NotionEntityDescription


@dataclass(frozen=True, kw_only=True)
class NotionSensorDescription(SensorEntityDescription, NotionEntityDescription):
    """Describe a Notion sensor."""


SENSOR_DESCRIPTIONS = (
    NotionSensorDescription(
        key=SENSOR_MOLD,
        translation_key="mold_risk",
        listener_kind=ListenerKind.MOLD,
    ),
    NotionSensorDescription(
        key=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        listener_kind=ListenerKind.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator: NotionDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NotionSensor(
                coordinator,
                listener_id,
                sensor.uuid,
                sensor.bridge.id,
                description,
            )
            for listener_id, listener in coordinator.data.listeners.items()
            for description in SENSOR_DESCRIPTIONS
            if description.listener_kind.value == listener.definition_id
            and (sensor := coordinator.data.sensors[listener.sensor_id])
        ]
    )


class NotionSensor(NotionEntity, SensorEntity):
    """Define a Notion sensor."""

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.listener.definition_id == ListenerKind.TEMPERATURE.value:
            if not self.coordinator.data.user_preferences:
                return None
            if self.coordinator.data.user_preferences.celsius_enabled:
                return UnitOfTemperature.CELSIUS
            return UnitOfTemperature.FAHRENHEIT
        return None

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        if not self.listener.status_localized:
            return None
        if self.listener.definition_id == ListenerKind.TEMPERATURE.value:
            # The Notion API only returns a localized string for temperature (e.g.
            # "70°"); we simply remove the degree symbol:
            return self.listener.status_localized.state[:-1]
        return self.listener.status_localized.state
