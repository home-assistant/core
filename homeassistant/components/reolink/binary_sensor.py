"""This component provides support for Reolink binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reolink_aio.api import (
    FACE_DETECTION_TYPE,
    PERSON_DETECTION_TYPE,
    PET_DETECTION_TYPE,
    VEHICLE_DETECTION_TYPE,
    Host,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkBinarySensorEntityDescriptionMixin:
    """Mixin values for Reolink binary sensor entities."""

    value: Callable[[Host, int | None], bool]


@dataclass
class ReolinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, ReolinkBinarySensorEntityDescriptionMixin
):
    """A class that describes binary sensor entities."""

    icon: str = "mdi:motion-sensor"
    icon_off: str = "mdi:motion-sensor-off"
    supported: Callable[[Host, int | None], bool] = lambda host, ch: True


BINARY_SENSORS = (
    ReolinkBinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda api, ch: api.motion_detected(ch),
    ),
    ReolinkBinarySensorEntityDescription(
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
        for entity_description in BINARY_SENSORS:
            if not entity_description.supported(host, channel):
                continue

            entities.append(
                ReolinkBinarySensorEntity(
                    reolink_data,
                    channel,
                    entity_description,
                )
            )

    async_add_entities(entities)


class ReolinkBinarySensorEntity(ReolinkCoordinatorEntity, BinarySensorEntity):
    """An implementation of a base binary-sensor class for Reolink IP camera motion sensors."""

    _attr_has_entity_name = True
    entity_description: ReolinkBinarySensorDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkBinarySensorDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        ReolinkCoordinatorEntity.__init__(self, reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def icon(self) -> str | None:
        """Icon of the sensor."""
        if self.entity_description.value(self._host, self._channel) is False:
            return self.entity_description.icon_off
        return super().icon

    @property
    def is_on(self) -> bool | None:
        """State of the sensor."""
        return self.entity_description.value(self._host, self._channel)

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._host.webhook_id}_{self._channel}",
                self._async_handle_event,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._host.webhook_id}_all",
                self._async_handle_event,
            )
        )

    async def _async_handle_event(self, event):
        """Handle incoming event for motion detection."""
        self.async_write_ha_state()
