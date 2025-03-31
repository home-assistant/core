"""Support for Netatmo binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NETATMO_CREATE_WEATHER_SENSOR
from .data_handler import NetatmoDevice
from .entity import NetatmoWeatherModuleEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_weather_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoWeatherBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_TYPES
            if description.key in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_binary_sensor_entity
        )
    )


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    def __init__(
        self, device: NetatmoDevice, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize a Netatmo binary sensor."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.reachable
        self.async_write_ha_state()
