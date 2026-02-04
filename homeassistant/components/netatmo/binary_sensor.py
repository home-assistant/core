"""Support for Netatmo binary sensors."""

from dataclasses import dataclass
import logging
from typing import Final, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import NETATMO_CREATE_WEATHER_BINARY_SENSOR
from .data_handler import NetatmoDevice
from .entity import NetatmoWeatherModuleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    name: str | None = None  # The default name of the sensor
    netatmo_name: str  # The name used by Netatmo API for this sensor


NETATMO_WEATHER_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        name="Connectivity",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo weather binary sensors based on a config entry."""

    @callback
    def _create_weather_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create weather binary sensor entities for a Netatmo weather device."""

        descriptions_to_add = NETATMO_WEATHER_BINARY_SENSOR_DESCRIPTIONS

        entities: list[NetatmoWeatherBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            # Actual check is simple for reachable
            feature_check = description.key
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    'Adding "%s" weather binary sensor for device %s',
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    NetatmoWeatherBinarySensor(
                        netatmo_device,
                        description,
                    )
                )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            NETATMO_CREATE_WEATHER_BINARY_SENSOR,
            _create_weather_binary_sensor_entity,
        )
    )


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo weather binary sensor."""

        super().__init__(netatmo_device)

        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        value: StateType | None = None

        value = getattr(self.device, self.entity_description.netatmo_name, None)

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        self.async_write_ha_state()
