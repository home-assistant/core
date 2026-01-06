"""Support for Netatmo binary sensors."""

from collections.abc import Callable
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

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_SECURITY,
    CONF_URL_WEATHER,
    NETATMO_CREATE_BINARY_SENSOR,
)
from .data_handler import NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    device_class_fn: Callable[[NetatmoDevice], BinarySensorDeviceClass] | None = None
    feature_name: str | None = None  # The feature key in the Module's features set
    name: str | None = None  # The default name of the sensor
    netatmo_name: str  # The name used by Netatmo API for this sensor
    value_fn: Callable[[StateType], StateType] = lambda x: x


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
    NetatmoDeviceCategory.climate: CONF_URL_ENERGY,
    NetatmoDeviceCategory.opening: CONF_URL_SECURITY,
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
        if netatmo_device.device.device_category is None:
            _LOGGER.warning(
                "Device %s is missing a device_category, cannot create binary sensors",
                netatmo_device.device.name,
            )
            return

        descriptions_to_add = NETATMO_BINARY_SENSOR_DESCRIPTIONS

        _LOGGER.debug(
            "Descriptions %s to add for module %s, features: %s",
            len(descriptions_to_add),
            netatmo_device.device.name,
            netatmo_device.device.features,
        )

        entities: list[NetatmoBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            if description.feature_name is None:
                feature_check = description.key
            else:
                feature_check = description.feature_name
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
            else:
                _LOGGER.warning(
                    "Failed to add %s (%s) binary sensor for device %s",
                    feature_check,
                    description.netatmo_name,
                    netatmo_device.device.name,
                )

        if entities:
            _LOGGER.debug(
                "Adding %s entities for device %s",
                len(entities),
                netatmo_device.device.name,
            )
            async_add_entities(entities)
        else:
            _LOGGER.debug(
                "No binary sensor entities created for device %s",
                netatmo_device.device.name,
            )

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
                    "Missing configuration URL for binary_sensor of %s device as category %s",
                    netatmo_device.device.name,
                    netatmo_device.device.device_category,
                )
                return
        else:
            _LOGGER.warning(
                "Device %s is missing a device_category, cannot set configuration URL for it's binary sensors",
                netatmo_device.device.name,
            )
            return

        super().__init__(netatmo_device)

        self.entity_description = description
        self._attr_unique_id = f"{netatmo_device.device.entity_id}-{description.key}"
        if description.device_class is not None:
            self.original_device_class = description.device_class
        if description.name is not None:
            self._attr_name = description.name
        if description.translation_key is not None:
            self._attr_translation_key = description.translation_key
        else:
            self._attr_translation_key = None

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

        _LOGGER.debug(
            "Initialized \"%s\" binary sensor (unique_id = %s) for module '%s'",
            self.entity_description.key,
            self._attr_unique_id,
            self.device.name,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        value: StateType = None
        raw_value: StateType = None

        raw_value = cast(
            StateType, getattr(self.device, self.entity_description.netatmo_name, None)
        )

        if raw_value is not None:
            value = self.entity_description.value_fn(raw_value)

            _LOGGER.debug(
                "\"%s\" translated from '%s' to '%s' for module '%s'",
                self.entity_description.netatmo_name,
                raw_value,
                value,
                self.device.name,
            )
        else:
            _LOGGER.warning(
                "No value can be found for \"%s\" for module '%s'",
                self.entity_description.netatmo_name,
                self.device.name,
            )

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        _LOGGER.debug(
            "Updating binary sensor '%s' for module '%s' with available=%s and status=%s",
            self.entity_description.key,
            self.device.name,
            self._attr_available,
            self._attr_is_on,
        )

        self.async_write_ha_state()
