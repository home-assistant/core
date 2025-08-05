"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

from pyatmo.modules import Module
from pyatmo.modules.device_types import DeviceCategory as NetatmoDeviceCategory

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NETATMO_CREATE_BINARY_SENSOR
from .data_handler import NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


def process_opening_status(device: Module) -> bool | None:
    """Process opening Module status and return bool."""
    status = device.status  # type: ignore[attr-defined]

    if status == "closed":
        return False
    if status in ["open", "not_detected"]:
        return True
    return None


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    netatmo_name: str | None = None
    value_fn: Callable[[Module], bool | None] = lambda device: None


NETATMO_BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        translation_key="reachable",
        netatmo_name=None,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda module: module.reachable,
    ),
)

OPENING_BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="open_status",
        translation_key="open_status",
        device_class=BinarySensorDeviceClass.OPENING,
        netatmo_name="Door Tag Status",
        value_fn=process_opening_status,
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
        entities = []

        if not hasattr(netatmo_device, "module") or not isinstance(
            netatmo_device.module, Module
        ):
            _LOGGER.debug(
                "Skipping device with no module attribute: %s", netatmo_device
            )
            return

        # Logic for creating opening sensors
        if netatmo_device.module.device_category == NetatmoDeviceCategory.opening:
            entities.extend(
                [
                    NetatmoBinarySensor(netatmo_device, description)
                    for description in OPENING_BINARY_SENSOR_TYPES
                ]
            )

        # Logic for creating common sensors (like reachable)
        entities.extend(
            [
                NetatmoBinarySensor(netatmo_device, description)
                for description in NETATMO_BINARY_SENSOR_TYPES
                if hasattr(netatmo_device.module, description.key)
            ]
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
        self, device: NetatmoDevice, description: NetatmoBinarySensorEntityDescription
    ) -> None:
        """Initialize a Netatmo binary sensor."""
        self.entity_description = description
        self._attr_translation_key = description.netatmo_name
        self._attr_unique_id = f"{device.device.entity_id}-{description.key}"

        if isinstance(description.netatmo_name, str):
            self._attr_translation_key = description.netatmo_name
        else:
            self._attr_translation_key = "Undefined"

        if hasattr(device.device, "url") and device.device.url:
            self._attr_configuration_url = device.device.url
        else:
            self._attr_configuration_url = ""

        super().__init__(device)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        status = None
        module = cast(Module, getattr(self.device, "module", None))

        if module:
            status = self.entity_description.value_fn(module)
            _LOGGER.debug(
                "Updating sensor '%s' for module '%s' with status: %s",
                self.entity_description.key,
                module.name,
                status,
            )

        self._attr_is_on = status
        self.async_write_ha_state()
