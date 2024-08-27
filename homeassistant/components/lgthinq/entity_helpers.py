"""LG ThinQ entity descriptions and mapping table."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import (
    PROPERTY_WRITABLE,
    DeviceType,
    ThinQAPIErrorCodes,
    ThinQAPIException,
)
from thinqconnect.devices.const import Property as propertyc
from thinqconnect.integration.homeassistant.property import Property, create_properties

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, POWER_OFF, POWER_ON
from .device import LGDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class PropertyInfo:
    """A data class contains an information for creating property."""

    # The property key for use in SDK must be snake_case string.
    key: str

    # Optional, if the value should be converted before calling api.
    value_converter: Callable[[Any], Any] | None = None


# Functions for entity operations.
def value_to_power_state_converter(value: Any) -> str:
    """Convert the value to string that represents power state."""
    return POWER_ON if bool(value) else POWER_OFF


@dataclass(kw_only=True, frozen=True)
class ThinQEntityDescription(SwitchEntityDescription):
    """The base thinq entity description."""

    has_entity_name = True
    property_info: PropertyInfo


OPERATION_SWITCH_DESC: dict[propertyc, ThinQEntityDescription] = {
    propertyc.AIR_FAN_OPERATION_MODE: ThinQEntityDescription(
        key=propertyc.AIR_FAN_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=propertyc.AIR_FAN_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    propertyc.AIR_PURIFIER_OPERATION_MODE: ThinQEntityDescription(
        key=propertyc.AIR_PURIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=propertyc.AIR_PURIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    propertyc.BOILER_OPERATION_MODE: ThinQEntityDescription(
        key=propertyc.BOILER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=propertyc.BOILER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    propertyc.DEHUMIDIFIER_OPERATION_MODE: ThinQEntityDescription(
        key=propertyc.DEHUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=propertyc.DEHUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    propertyc.HUMIDIFIER_OPERATION_MODE: ThinQEntityDescription(
        key=propertyc.HUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=propertyc.HUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
}
# AIR_PURIFIER_FAN Description
AIR_PURIFIER_FAN_SWITCH: tuple[ThinQEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[propertyc.AIR_FAN_OPERATION_MODE],
)
# AIRPURIFIER Description
AIRPURIFIER_SWITCH: tuple[ThinQEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[propertyc.AIR_PURIFIER_OPERATION_MODE],
)
# DEHUMIDIFIER Description
DEHUMIDIFIER_SWITCH: tuple[ThinQEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[propertyc.DEHUMIDIFIER_OPERATION_MODE],
)
# HUMIDIFIER Description
HUMIDIFIER_SWITCH: tuple[ThinQEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[propertyc.HUMIDIFIER_OPERATION_MODE],
)
# SYSTEM_BOILER Description
SYSTEM_BOILER_SWITCH: tuple[ThinQEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[propertyc.BOILER_OPERATION_MODE],
)


# The entity escription map for each device type.
ENTITY_MAP = {
    DeviceType.AIR_PURIFIER_FAN: {Platform.SWITCH: AIR_PURIFIER_FAN_SWITCH},
    DeviceType.AIR_PURIFIER: {Platform.SWITCH: AIRPURIFIER_SWITCH},
    DeviceType.DEHUMIDIFIER: {Platform.SWITCH: DEHUMIDIFIER_SWITCH},
    DeviceType.HUMIDIFIER: {Platform.SWITCH: HUMIDIFIER_SWITCH},
}

READ_WRITE_TYPE: dict[str, str] = {
    Platform.SWITCH: PROPERTY_WRITABLE,
}


def get_property_list(
    device: LGDevice, target_platform: Platform
) -> dict[Property, ThinQEntityDescription] | None:
    """Get property list with description."""
    desc_map = ENTITY_MAP.get(device.api.device_type)
    if not isinstance(desc_map, dict):
        return None

    desc_list = desc_map.get(target_platform)
    if not isinstance(desc_list, (list, tuple)):
        return None

    # Get entitiy descriptions for the target platform.
    prop_list: dict[Property, ThinQEntityDescription] = {}
    for desc in desc_list:
        properties = create_properties(
            device_api=device.api,
            key=desc.key,
            children_keys=None,
            mode=None,
            rw_type=READ_WRITE_TYPE.get(target_platform),
        )

        if not properties:
            continue

        for prop in properties:
            prop_list[prop] = desc
            _LOGGER.debug(
                "[%s] Add %s entity for [%s]",
                device.name,
                target_platform,
                desc.key,
            )

    return prop_list


class ThinQEntity(CoordinatorEntity):
    """The base implementation of all lg thinq entities."""

    entity_description: ThinQEntityDescription

    def __init__(
        self,
        device: LGDevice,
        property: Property,
        entity_description: ThinQEntityDescription,
    ) -> None:
        """Initialize an entity."""
        super().__init__(device.coordinator)

        self._device = device
        self._property = property
        self.entity_description = entity_description
        self._attr_device_info = device.device_info

        # If there exist a location, add the prefix location name.
        location = self.property.location

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

    def get_property(self) -> Property | None:
        """Return the property corresponding to the feature."""
        return self.property

    def get_value_as_bool(self) -> bool:
        """Return the property value of entity as bool."""
        prop = self.get_property()
        return prop.get_value_as_bool() if prop is not None else False

    async def async_post_value(self, value: Any) -> None:
        """Post the value of entity to server."""
        prop = self.get_property()
        if prop is None:
            return
        try:
            await prop.async_post_value(value)
        except ThinQAPIException as exc:
            if exc.code == ThinQAPIErrorCodes.NOT_CONNECTED_DEVICE:
                self.device.is_connected = False
            # Rollback device's status data.
            self.device.coordinator.async_set_updated_data({})

            raise ServiceValidationError(
                exc.message,
                translation_domain=DOMAIN,
                translation_key=exc.code,
            ) from exc

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
