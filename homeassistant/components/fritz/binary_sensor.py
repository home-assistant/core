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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    AvmWrapper,
    ConnectionInfo,
    FritzBoxBaseCoordinatorEntity,
    FritzEntityDescription,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FritzBinarySensorEntityDescription(
    BinarySensorEntityDescription, FritzEntityDescription
):
    """Describes Fritz sensor entity."""

    is_suitable: Callable[[ConnectionInfo], bool] = lambda info: info.wan_enabled


SENSOR_TYPES: tuple[FritzBinarySensorEntityDescription, ...] = (
    FritzBinarySensorEntityDescription(
        key="is_connected",
        translation_key="is_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status, _: bool(status.is_connected),
    ),
    FritzBinarySensorEntityDescription(
        key="is_linked",
        translation_key="is_linked",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status, _: bool(status.is_linked),
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


class FritzBoxBinarySensor(FritzBoxBaseCoordinatorEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    entity_description: FritzBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if isinstance(
            state := self.coordinator.data["entity_states"].get(
                self.entity_description.key
            ),
            bool,
        ):
            return state
        return None
