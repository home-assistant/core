"""AVM FRITZ!Box connectivity sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import AvmWrapper, ConnectionInfo, FritzBoxBaseEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FritzBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Fritz sensor entity."""

    is_suitable: Callable[[ConnectionInfo], bool] = lambda info: info.wan_enabled


SENSOR_TYPES: tuple[FritzBinarySensorEntityDescription, ...] = (
    FritzBinarySensorEntityDescription(
        key="is_connected",
        name="Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FritzBinarySensorEntityDescription(
        key="is_linked",
        name="Link",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FritzBinarySensorEntityDescription(
        # Deprecated, scheduled to be removed in 2022.7 (#70096)
        entity_registry_enabled_default=False,
        key="firmware_update",
        name="Firmware Update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_suitable=lambda info: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box binary sensors")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    connection_info = await avm_wrapper.async_get_connection_info()

    entities = [
        FritzBoxBinarySensor(avm_wrapper, entry.title, description)
        for description in SENSOR_TYPES
        if description.is_suitable(connection_info)
    ]

    async_add_entities(entities, True)


class FritzBoxBinarySensor(FritzBoxBaseEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self.entity_description = description
        self._attr_name = f"{device_friendly_name} {description.name}"
        self._attr_unique_id = f"{avm_wrapper.unique_id}-{description.key}"
        super().__init__(avm_wrapper, device_friendly_name)

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box binary sensors")

        if self.entity_description.key == "firmware_update":
            self._attr_is_on = self._avm_wrapper.update_available
            self._attr_extra_state_attributes = {
                "installed_version": self._avm_wrapper.current_firmware,
                "latest_available_version": self._avm_wrapper.latest_firmware,
            }
        if self.entity_description.key == "is_connected":
            self._attr_is_on = bool(self._avm_wrapper.fritz_status.is_connected)
        elif self.entity_description.key == "is_linked":
            self._attr_is_on = bool(self._avm_wrapper.fritz_status.is_linked)
