"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from pyatmo.modules import Module
from pyatmo.modules.device_types import DeviceCategory as NetatmoDeviceCategory

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_SECURITY,
    CONF_URL_WEATHER,
    NETATMO_CREATE_BINARY_SENSOR,
)
from .data_handler import NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


def process_opening_status(module: Module) -> bool | None:
    """Process opening Module status and return bool."""
    status = module.status  # type: ignore[attr-defined]

    if status == "closed":
        return False
    if status in ["open", "not_detected", "no_news"]:
        return True
    return None


def process_opening_category(netatmo_device: NetatmoDevice) -> BinarySensorDeviceClass:
    """Helper function to map Netatmo category to Home Assistant device class."""

    # First, get the unique ID of the device we are processing.
    device_id_to_find = netatmo_device.device.entity_id

    # Get the raw data containing the full list of homes and modules.
    raw_data = netatmo_device.data_handler.account.raw_data

    # Iterate through each home in the raw data.
    for home in raw_data["homes"]:
        # Check if the modules list exists for the current home.
        if "modules" in home:
            # Iterate through each module to find a matching ID.
            for module in home["modules"]:
                if module["id"] == device_id_to_find:
                    # We found the matching device. Get its category.
                    category = module.get("category")

                    _LOGGER.debug(
                        "Processing category '%s' for device '%s'",
                        category,
                        netatmo_device.device.name,
                    )

                    # Use a specific device class if we have a match
                    if category == "door":
                        return BinarySensorDeviceClass.DOOR
                    if category == "window":
                        return BinarySensorDeviceClass.WINDOW
                    if category == "garage":
                        return BinarySensorDeviceClass.GARAGE_DOOR
                    if category == "gate":
                        return BinarySensorDeviceClass.OPENING
                    if category == "furniture":
                        return BinarySensorDeviceClass.OPENING
                    if category == "other":
                        return BinarySensorDeviceClass.OPENING

    # Return None if the device or category is not found in the raw data.
    _LOGGER.warning(
        "Category not found for device_id: %s in raw data",
        netatmo_device.device.name,
    )
    return BinarySensorDeviceClass.OPENING


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    category_fn: Callable[[NetatmoDevice], BinarySensorDeviceClass] | None = None
    netatmo_name: str | None = None
    value_fn: Callable[[Module], bool | None] = lambda device: None


NETATMO_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        translation_key="Reachability",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda module: module.reachable,
        icon="mdi:signal",
    ),
]

OPENING_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="open_status",
        translation_key="Opening",
        device_class=BinarySensorDeviceClass.OPENING,
        netatmo_name="status",
        value_fn=process_opening_status,
        category_fn=process_opening_category,
    ),
]

DEVICE_CATEGORY_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.opening: OPENING_BINARY_SENSOR_DESCRIPTIONS,
}

DEVICE_CATEGORY_BINARY_URLS: Final[dict[NetatmoDeviceCategory, str]] = {
    NetatmoDeviceCategory.opening: CONF_URL_SECURITY,
    NetatmoDeviceCategory.weather: CONF_URL_WEATHER,
    NetatmoDeviceCategory.climate: CONF_URL_ENERGY,
}

DEVICE_CLASS_TRANSLATIONS: Final[dict[BinarySensorDeviceClass, str]] = {
    BinarySensorDeviceClass.OPENING: "Opening",
    BinarySensorDeviceClass.DOOR: "Door",
    BinarySensorDeviceClass.WINDOW: "Window",
    BinarySensorDeviceClass.GARAGE_DOOR: "Garage Door",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create new binary sensor entities."""

        if not isinstance(netatmo_device.device, Module):
            _LOGGER.debug(
                "Skipping device that is not a module: %s",
                netatmo_device.device.name,
            )
            return

        if netatmo_device.device.device_category is None:
            _LOGGER.warning(
                "Device %s is missing a device_category, cannot create binary sensors",
                netatmo_device.device.name,
            )
            return

        descriptions_to_add = (
            NETATMO_BINARY_SENSOR_DESCRIPTIONS
            + DEVICE_CATEGORY_BINARY_SENSORS.get(
                netatmo_device.device.device_category, []
            )
        )

        _LOGGER.debug(
            "Descriptions %s to add for module %s, features: %s",
            len(descriptions_to_add),
            netatmo_device.device.name,
            netatmo_device.device.features,
        )

        entities: list[NetatmoBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            if description.netatmo_name in netatmo_device.device.features:
                _LOGGER.debug(
                    "Adding %s binary sensor for device %s",
                    description.netatmo_name,
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
                    description.netatmo_name,
                    description.key,
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
    _attr_has_entity_name = True

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo binary sensor."""

        if not isinstance(netatmo_device.device, Module):
            return

        if description.category_fn:
            self._attr_device_class = description.category_fn(netatmo_device)
        else:
            self._attr_device_class = description.device_class
        if self._attr_device_class is None:
            return
        name_suffix = DEVICE_CLASS_TRANSLATIONS.get(self._attr_device_class)
        if not name_suffix:
            name_suffix = (
                description.translation_key
                if description.translation_key
                else description.key.replace("_", " ").title()
            )

        self._attr_unique_id = f"{netatmo_device.device.entity_id}-{description.key}"
        self._attr_name = name_suffix
        if netatmo_device.device.device_category:
            self._attr_configuration_url = DEVICE_CATEGORY_BINARY_URLS.get(
                netatmo_device.device.device_category, None
            )
        else:
            self._attr_configuration_url = None

        super().__init__(netatmo_device)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        value = None
        module = self.device

        if not module or not module.reachable:
            if self.available:
                self._attr_available = False
            self.async_write_ha_state()
            return

        value = self.entity_description.value_fn(module)
        _LOGGER.debug(
            "Updating sensor '%s' for module '%s' with status: %s",
            self.entity_description.netatmo_name,
            module.name,
            value,
        )

        self._attr_available = True
        self._attr_is_on = value
        self.async_write_ha_state()
