"""Support for Notion sensors."""
from dataclasses import dataclass

from aionotion.sensor.models import ListenerKind

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NotionEntity
from .const import DOMAIN, SENSOR_MOLD, SENSOR_TEMPERATURE
from .model import NotionEntityDescriptionMixin


@dataclass
class NotionSensorDescription(SensorEntityDescription, NotionEntityDescriptionMixin):
    """Describe a Notion sensor."""


SENSOR_DESCRIPTIONS = (
    NotionSensorDescription(
        key=SENSOR_MOLD,
        translation_key="mold_risk",
        icon="mdi:liquid-spot",
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
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NotionSensor(
                coordinator,
                listener_id,
                sensor.uuid,
                sensor.bridge.id,
                sensor.system_id,
                description,
            )
            for listener_id, listener in coordinator.data.listeners.items()
            for description in SENSOR_DESCRIPTIONS
            if description.listener_kind == listener.listener_kind
            and (sensor := coordinator.data.sensors[listener.sensor_id])
        ]
    )


class NotionSensor(NotionEntity, SensorEntity):
    """Define a Notion sensor."""

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.listener.listener_kind == ListenerKind.TEMPERATURE:
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
        if self.listener.listener_kind == ListenerKind.TEMPERATURE:
            # The Notion API only returns a localized string for temperature (e.g.
            # "70°"); we simply remove the degree symbol:
            return self.listener.status_localized.state[:-1]
        return self.listener.status_localized.state
