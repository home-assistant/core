"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyatmo.modules import Module

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

from .const import CONF_URL_SECURITY, NETATMO_CREATE_BINARY_SENSOR
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

    # Return None if the device or category is not found in the raw data.
    _LOGGER.warning(
        "Category not found for device_id: %s in raw data",
        netatmo_device.device.name,
    )
    return BinarySensorDeviceClass.OPENING


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    netatmo_name: str | None = None
    value_fn: Callable[[Module], bool | None] = lambda device: None
    category_fn: Callable[[NetatmoDevice], BinarySensorDeviceClass] | None = None


NETATMO_BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        translation_key="reachable",
        netatmo_name="Reachability",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda module: module.reachable,
    ),
)

OPENING_BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="open_status",
        translation_key="open_status",
        device_class=BinarySensorDeviceClass.OPENING,
        netatmo_name="Opening",
        value_fn=process_opening_status,
        category_fn=process_opening_category,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create new binary sensor entities."""
        entities: list[NetatmoBinarySensor] = []

        if not hasattr(netatmo_device, "module") or not isinstance(
            netatmo_device.module, Module
        ):
            _LOGGER.debug(
                "Skipping device with no module attribute: %s", netatmo_device
            )
            return

        entities.extend(
            NetatmoBinarySensor(netatmo_device, description)
            for description in NETATMO_BINARY_SENSOR_TYPES
        )

        if hasattr(netatmo_device.module, "status"):
            entities.extend(
                NetatmoBinarySensor(netatmo_device, description)
                for description in OPENING_BINARY_SENSOR_TYPES
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
        name_suffix = (
            description.netatmo_name or description.key.replace("_", " ").title()
        )

        self._attr_unique_id = f"{netatmo_device.device.entity_id}-{description.key}"
        self._attr_name = name_suffix
        self._attr_configuration_url = CONF_URL_SECURITY
        if description.category_fn:
            self._attr_device_class = description.category_fn(netatmo_device)
        else:
            self._attr_device_class = description.device_class

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
            self.entity_description.key,
            module.name,
            value,
        )

        self._attr_available = True
        self._attr_is_on = value
        self.async_write_ha_state()
