"""The Flexit Nordic (BACnet) integration."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from flexit_bacnet import FlexitBACnet

from homeassistant.components.binary_sensor import (
    DOMAIN as SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...helpers.update_coordinator import CoordinatorEntity
from . import FlexitCoordinator
from .const import DOMAIN
from .entity import FlexitEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_SENSOR_FORMAT = (
    SENSOR_DOMAIN + ".{}_{}"
)  # should use f"{some_value} {some_other_value}"


@dataclass(kw_only=True, frozen=True)
class FlexitBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Flexit binary sensor entity."""

    value_fn: Callable[[FlexitBACnet], bool]


SENSOR_TYPES: tuple[FlexitBinarySensorEntityDescription, ...] = (
    FlexitBinarySensorEntityDescription(
        key="electric_heater",
        device_class=BinarySensorDeviceClass.HEAT,
        translation_key="electric_heater",
        value_fn=lambda data: data.electric_heater,
    ),
    FlexitBinarySensorEntityDescription(
        key="air_filter_polluted",
        device_class=BinarySensorDeviceClass.PROBLEM,  # What should be used for this sensor?
        translation_key="air_filter_polluted",
        value_fn=lambda data: data.air_filter_polluted,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) binary sensor from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.info("Setting up Flexit (bacnet) sensor from a config entry")

    async_add_entities(
        [
            FlexitBinarySensor(coordinator, description, config_entry.entry_id)
            for description in SENSOR_TYPES
        ]
    )

    # TODO: unsubscribe on remove


class FlexitBinarySensor(FlexitEntity, CoordinatorEntity, BinarySensorEntity):
    """Representation of a Flexit binary Sensor."""

    # Should it have a name?
    # _attr_name = None

    # Should it have a entity_name?
    # _attr_has_entity_name = True

    # Poll is default

    entity_description: FlexitBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitBinarySensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize Flexit (bacnet) sensor."""
        super().__init__(coordinator)

        _LOGGER.info(
            "Initialize Flexit (bacnet) binary sensor %s", entity_description.key
        )

        self.entity_description = entity_description
        self.entity_id = ENTITY_ID_SENSOR_FORMAT.format(
            coordinator.device.device_name, entity_description.key
        )
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return value of binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
