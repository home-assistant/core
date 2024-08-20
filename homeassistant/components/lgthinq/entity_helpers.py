"""LG ThinQ entity descriptions and mapping table."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum, unique
import logging
from typing import Any, Generic, TypeVar

from thinqconnect import DeviceType

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import POWER_OFF, POWER_ON
from .device import LGDevice
from .property import Property, PropertyFeature, PropertyInfo, Range, create_properties
from .switch import ThinQSwitchEntity

_LOGGER = logging.getLogger(__name__)


def value_to_power_state_converter(value: Any) -> str:
    """Convert the value to string that represents power state."""
    return POWER_ON if bool(value) else POWER_OFF


# Type hints for lg thinq entity.
ThinQEntityT = TypeVar("ThinQEntityT", bound="ThinQEntity")
ThinQEntityDescriptionT = TypeVar(
    "ThinQEntityDescriptionT", bound="ThinQEntityDescription"
)


@dataclass(kw_only=True, frozen=True)
class ThinQEntityDescription(EntityDescription):
    """The base thinq entity description."""

    has_entity_name = True
    property_info: PropertyInfo


@dataclass(kw_only=True, frozen=True)
class ThinQSwitchEntityDescription(ThinQEntityDescription, SwitchEntityDescription):
    """The entity description for switch."""


@unique
class Operation(StrEnum):
    """Properties in 'operation' module."""

    AIR_FAN_OPERATION_MODE = "air_fan_operation_mode"
    AIR_PURIFIER_OPERATION_MODE = "air_purifier_operation_mode"
    DEHUMIDIFIER_OPERATION_MODE = "dehumidifier_operation_mode"
    HUMIDIFIER_OPERATION_MODE = "humidifier_operation_mode"


OPERATION_SWITCH_DESC: dict[Operation, ThinQSwitchEntityDescription] = {
    Operation.AIR_FAN_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.AIR_FAN_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.AIR_FAN_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    Operation.AIR_PURIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.AIR_PURIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.AIR_PURIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    Operation.DEHUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.DEHUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.DEHUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    Operation.HUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.HUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.HUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
}

AIR_PURIFIER_FAN_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.AIR_FAN_OPERATION_MODE],
)
AIRPURIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.AIR_PURIFIER_OPERATION_MODE],
)
DEHUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.DEHUMIDIFIER_OPERATION_MODE],
)
HUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.HUMIDIFIER_OPERATION_MODE],
)


# The entity escription map for each device type.
ENTITY_MAP = {
    DeviceType.AIR_PURIFIER_FAN: {Platform.SWITCH: AIR_PURIFIER_FAN_SWITCH},
    DeviceType.AIR_PURIFIER: {Platform.SWITCH: AIRPURIFIER_SWITCH},
    DeviceType.DEHUMIDIFIER: {Platform.SWITCH: DEHUMIDIFIER_SWITCH},
    DeviceType.HUMIDIFIER: {Platform.SWITCH: HUMIDIFIER_SWITCH},
}

UNIT_CONVERSION_MAP: dict[str, str] = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}


class ThinQEntity(CoordinatorEntity, Generic[ThinQEntityDescriptionT]):
    """The base implementation of all lg thinq entities."""

    target_platform: Platform | None
    entity_description: ThinQEntityDescriptionT

    def __init__(
        self,
        device: LGDevice,
        property: Property,
        entity_description: ThinQEntityDescriptionT,
    ) -> None:
        """Initialize an entity."""
        super().__init__(device.coordinator)

        self._device = device
        self._property = property
        self.entity_description = entity_description
        self._attr_device_info = device.device_info

        # If there exist a location, add the prefix location name.
        location = self.property.location
        location_str = (
            ""
            if location is None or location in ("main", "oven", device.sub_id)
            else f"{location} "
        )
        self._attr_translation_placeholders = {"location": location_str}

        # Set the unique key.
        unique_key = (
            f"{entity_description.key}"
            if location is None
            else f"{location}_{entity_description.key}"
        )
        self._attr_unique_id = f"{device.unique_id}_{unique_key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_connected

    @property
    def device(self) -> LGDevice:
        """Return the connected device."""
        return self._device

    @property
    def property(self) -> Property:
        """Return the property of entity."""
        return self._property

    def get_property(self, feature: PropertyFeature | None = None) -> Property | None:
        """Return the property corresponding to the feature."""
        if feature is None:
            return self.property

        return self.property.get_featured_property(feature)

    def get_options(self, feature: PropertyFeature | None = None) -> list[str] | None:
        """Return the property options of entity."""
        prop = self.get_property(feature)
        return prop.options if prop is not None else None

    def get_range(self, feature: PropertyFeature | None = None) -> Range | None:
        """Return the property range of entity."""
        prop = self.get_property(feature)
        return prop.range if prop is not None else None

    def get_unit(self, feature: PropertyFeature | None = None) -> str | None:
        """Return the property unit of entity."""
        prop = self.get_property(feature)
        return prop.unit if prop is not None else None

    def get_value(self, feature: PropertyFeature | None = None) -> Any:
        """Return the property value of entity."""
        prop = self.get_property(feature)
        return prop.get_value() if prop is not None else None

    def get_value_as_bool(self, feature: PropertyFeature | None = None) -> bool:
        """Return the property value of entity as bool."""
        prop = self.get_property(feature)
        return prop.get_value_as_bool() if prop is not None else False

    async def async_post_value(
        self, value: Any, feature: PropertyFeature | None = None
    ) -> None:
        """Post the value of entity to server."""
        prop = self.get_property(feature)
        if prop is not None:
            await prop.async_post_value(value)

    def _get_unit_of_measurement(
        self, unit: str | None, fallback: str | None
    ) -> str | None:
        """Convert ThinQ unit string to HA unit string."""
        if unit is None:
            return fallback

        return UNIT_CONVERSION_MAP.get(unit, fallback)

    def _update_status(self) -> None:
        """Update status itself.

        All inherited classes can update their own status in here.
        """

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_status()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @classmethod
    def create_entities(cls, devices: Collection[LGDevice]) -> list[ThinQEntity]:
        """Create entities with descriptions from the entity map."""
        if not devices or cls.target_platform is None:
            return []

        _LOGGER.debug(
            "async_create_entities. cls=%s, target_platform=%s",
            cls.__name__,
            cls.target_platform,
        )

        entities: list[ThinQEntity] = []
        for device in devices:
            entities_for_device = cls.create_entities_for_device(device)
            if entities_for_device:
                entities.extend(entities_for_device)

        return entities

    @classmethod
    def create_entities_for_device(cls, device: LGDevice) -> list[ThinQEntity] | None:
        """Create entities for the device."""
        if cls.target_platform is None:
            return None

        # Get the entitiy description map for the device type.
        desc_map = ENTITY_MAP.get(device.type)
        if not isinstance(desc_map, dict):
            return None

        # Get entitiy descriptions for the target platform.
        desc_list = desc_map.get(cls.target_platform)
        if not isinstance(desc_list, (list, tuple)):
            return None

        if not desc_list:
            return None

        entities: list[ThinQEntity] = []
        # Try to create entities for all entity descriptions.
        for desc in desc_list:
            properties = create_properties(
                device, desc.property_info, cls.target_platform
            )
            if not properties:
                continue

            for prop in properties:
                if cls != ThinQSwitchEntity:
                    continue

                entities.append(ThinQSwitchEntity(device, prop, desc))

                _LOGGER.debug(
                    "[%s] Add %s entity for [%s]",
                    device.name,
                    cls.target_platform,
                    desc.key,
                )

        return entities
