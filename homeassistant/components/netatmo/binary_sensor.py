"""Support for Netatmo binary sensors."""

from dataclasses import dataclass
import logging
from typing import Final, cast

from pyatmo.modules.base_class import Place
from pyatmo.modules.device_types import DeviceCategory as NetatmoDeviceCategory

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_URL_WEATHER, NETATMO_CREATE_BINARY_SENSOR, SIGNAL_NAME
from .data_handler import NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    name: str | None = None  # The default name of the sensor
    netatmo_name: str  # The name used by Netatmo API for this sensor


NETATMO_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        name="Connectivity",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
]

DEVICE_CATEGORY_BINARY_URLS: Final[dict[NetatmoDeviceCategory, str]] = {
    NetatmoDeviceCategory.air_care: CONF_URL_WEATHER,
    NetatmoDeviceCategory.weather: CONF_URL_WEATHER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create binary sensor entities for a Netatmo device."""

        descriptions_to_add = NETATMO_BINARY_SENSOR_DESCRIPTIONS

        entities: list[NetatmoBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            # Actual check is simple for reachable
            feature_check = description.key
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    'Adding "%s" binary sensor for device %s',
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    NetatmoBinarySensor(
                        netatmo_device,
                        description,
                    )
                )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_BINARY_SENSOR, _create_binary_sensor_entity
        )
    )


class NetatmoBinarySensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo binary sensor."""

        if netatmo_device.device.device_category is not None:
            if (
                DEVICE_CATEGORY_BINARY_URLS.get(netatmo_device.device.device_category)
                is not None
            ):
                self._attr_configuration_url = DEVICE_CATEGORY_BINARY_URLS[
                    netatmo_device.device.device_category
                ]
            else:
                _LOGGER.warning(
                    "Missing configuration URL for binary_sensor of %s device as category %s. Please report this issue",
                    netatmo_device.device.name,
                    netatmo_device.device.device_category,
                )
                return

        super().__init__(netatmo_device)

        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

        # For historical reasons, entities should have publisher set
        # as binary_sensors were handled as NETATMO_CREATE_WEATHER_SENSOR earlier
        assert self.device.device_category
        category = self.device.device_category.name
        self._publishers.extend(
            [
                {
                    "name": category,
                    SIGNAL_NAME: category,
                },
            ]
        )

        # For historical reasons, entities should have location set
        # as binary_sensors were handled as NETATMO_CREATE_WEATHER_SENSOR earlier
        if hasattr(netatmo_device.device, "place"):
            place = cast(Place, netatmo_device.device.place)
            if hasattr(place, "location") and place.location is not None:
                self._attr_extra_state_attributes.update(
                    {
                        ATTR_LATITUDE: place.location.latitude,
                        ATTR_LONGITUDE: place.location.longitude,
                    }
                )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        value: StateType = None

        value = getattr(self.device, self.entity_description.netatmo_name, None)

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        self.async_write_ha_state()
