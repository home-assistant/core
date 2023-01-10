"""This component provides support for Reolink binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from reolink_ip.api import (
    FACE_DETECTION_TYPE,
    PERSON_DETECTION_TYPE,
    PET_DETECTION_TYPE,
    VEHICLE_DETECTION_TYPE,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReolinkBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes binary sensor entities."""

    icon: str = "mdi:motion-sensor"
    icon_off: str = "mdi:motion-sensor-off"
    value: Callable = lambda host, ch: None
    supported: Callable = lambda host, ch: True


BINARY_SENSORS = (
    ReolinkBinarySensorDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda host, ch: host.api.motion_detected(ch),
    ),
    ReolinkBinarySensorDescription(
        key=FACE_DETECTION_TYPE,
        name=FACE_DETECTION_TYPE,
        icon="mdi:face-recognition",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda host, ch: host.api.ai_detected(ch, FACE_DETECTION_TYPE),
        supported=lambda host, ch: host.api.ai_supported(ch, FACE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorDescription(
        key=PERSON_DETECTION_TYPE,
        name=PERSON_DETECTION_TYPE,
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda host, ch: host.api.ai_detected(ch, PERSON_DETECTION_TYPE),
        supported=lambda host, ch: host.api.ai_supported(ch, PERSON_DETECTION_TYPE),
    ),
    ReolinkBinarySensorDescription(
        key=VEHICLE_DETECTION_TYPE,
        name=VEHICLE_DETECTION_TYPE,
        icon="mdi:car",
        icon_off="mdi:car-off",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda host, ch: host.api.ai_detected(ch, VEHICLE_DETECTION_TYPE),
        supported=lambda host, ch: host.api.ai_supported(ch, VEHICLE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorDescription(
        key=PET_DETECTION_TYPE,
        name=PET_DETECTION_TYPE,
        icon="mdi:dog-side",
        icon_off="mdi:dog-side-off",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda host, ch: host.api.ai_detected(ch, PET_DETECTION_TYPE),
        supported=lambda host, ch: host.api.ai_supported(ch, PET_DETECTION_TYPE),
    ),
    ReolinkBinarySensorDescription(
        key="visitor",
        name="Visitor",
        icon="mdi:bell-ring-outline",
        icon_off="mdi:doorbell",
        value=lambda host, ch: host.api.visitor_detected(ch),
        supported=lambda host, ch: host.api.is_doorbell_enabled(ch),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]
    host = reolink_data.host

    entities = []
    for channel in host.api.channels:
        for description in BINARY_SENSORS:
            if not description.supported(host, channel):
                continue

            entities.append(
                ReolinkBinarySensorEntity(
                    reolink_data,
                    channel,
                    description,
                )
            )

    async_add_entities(entities, update_before_add=True)


class ReolinkBinarySensorEntity(ReolinkCoordinatorEntity, BinarySensorEntity):
    """An implementation of a base binary-sensor class for Reolink IP camera motion sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        description: ReolinkBinarySensorDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        ReolinkCoordinatorEntity.__init__(self, reolink_data, channel)
        BinarySensorEntity.__init__(self)

        self._description = description

        self._attr_name = description.name
        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{description.key}"
        )
        self._attr_device_class = description.device_class

    @property
    def icon(self) -> str:
        """Icon of the sensor."""
        if self.is_on:
            return self._description.icon

        return self._description.icon_off

    @property
    def is_on(self) -> bool:
        """State of the sensor."""
        return self._description.value(self._host, self._channel)

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        self.hass.bus.async_listen(
            f"{self._host.webhook_id}_{self._channel}", self.handle_event
        )
        self.hass.bus.async_listen(f"{self._host.webhook_id}_all", self.handle_event)

    async def handle_event(self, event):
        """Handle incoming event for motion detection."""
        await self.async_write_ha_state()
