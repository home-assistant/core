"""Component providing support for Reolink binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reolink_aio.api import (
    DUAL_LENS_DUAL_MOTION_MODELS,
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
from .entity import ReolinkChannelCoordinatorEntity


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
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda api, ch: api.motion_detected(ch),
    ),
    ReolinkBinarySensorEntityDescription(
        key=FACE_DETECTION_TYPE,
        translation_key="face",
        icon="mdi:face-recognition",
        value=lambda api, ch: api.ai_detected(ch, FACE_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, FACE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PERSON_DETECTION_TYPE,
        translation_key="person",
        value=lambda api, ch: api.ai_detected(ch, PERSON_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, PERSON_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=VEHICLE_DETECTION_TYPE,
        translation_key="vehicle",
        icon="mdi:car",
        icon_off="mdi:car-off",
        value=lambda api, ch: api.ai_detected(ch, VEHICLE_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, VEHICLE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PET_DETECTION_TYPE,
        translation_key="pet",
        icon="mdi:dog-side",
        icon_off="mdi:dog-side-off",
        value=lambda api, ch: api.ai_detected(ch, PET_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, PET_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key="visitor",
        translation_key="visitor",
        icon="mdi:bell-ring-outline",
        icon_off="mdi:doorbell",
        value=lambda api, ch: api.visitor_detected(ch),
        supported=lambda api, ch: api.is_doorbell(ch),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ReolinkBinarySensorEntity] = []
    for channel in reolink_data.host.api.channels:
        entities.extend(
            [
                ReolinkBinarySensorEntity(reolink_data, channel, entity_description)
                for entity_description in BINARY_SENSORS
                if entity_description.supported(reolink_data.host.api, channel)
            ]
        )

    async_add_entities(entities)


class ReolinkBinarySensorEntity(ReolinkChannelCoordinatorEntity, BinarySensorEntity):
    """Base binary-sensor class for Reolink IP camera motion sensors."""

    entity_description: ReolinkBinarySensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        if self._host.api.model in DUAL_LENS_DUAL_MOTION_MODELS:
            name = self.platform.platform_translations.get(self._name_translation_key)
            self._attr_name = f"{name} lens {self._channel}"

        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def icon(self) -> str | None:
        """Icon of the sensor."""
        if self.is_on is False:
            return self.entity_description.icon_off
        return super().icon

    @property
    def is_on(self) -> bool:
        """State of the sensor."""
        return self.entity_description.value(self._host.api, self._channel)

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
