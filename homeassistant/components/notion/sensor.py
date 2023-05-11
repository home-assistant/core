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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NotionEntity
from .const import DOMAIN, LOGGER, SENSOR_TEMPERATURE
from .model import NotionEntityDescriptionMixin


@dataclass
class NotionSensorDescription(SensorEntityDescription, NotionEntityDescriptionMixin):
    """Describe a Notion sensor."""


SENSOR_DESCRIPTIONS = (
    NotionSensorDescription(
        key=SENSOR_TEMPERATURE,
        name="Temperature",
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

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        listener = self.coordinator.data.listeners[self._listener_id]

        if listener.listener_kind == ListenerKind.TEMPERATURE:
            self._attr_native_value = round(listener.status.temperature, 1)  # type: ignore[attr-defined]
        else:
            LOGGER.error(
                "Unknown listener type for sensor %s",
                self.coordinator.data.sensors[self._sensor_id],
            )
