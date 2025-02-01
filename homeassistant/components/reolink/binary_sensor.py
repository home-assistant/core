"""Component providing support for Reolink binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reolink_aio.api import (
    DUAL_LENS_DUAL_MOTION_MODELS,
    FACE_DETECTION_TYPE,
    PACKAGE_DETECTION_TYPE,
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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ReolinkChannelCoordinatorEntity, ReolinkChannelEntityDescription
from .util import ReolinkConfigEntry, ReolinkData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes binary sensor entities."""

    value: Callable[[Host, int], bool]


BINARY_PUSH_SENSORS = (
    ReolinkBinarySensorEntityDescription(
        key="motion",
        cmd_id=33,
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda api, ch: api.motion_detected(ch),
    ),
    ReolinkBinarySensorEntityDescription(
        key=FACE_DETECTION_TYPE,
        cmd_id=33,
        translation_key="face",
        value=lambda api, ch: api.ai_detected(ch, FACE_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, FACE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PERSON_DETECTION_TYPE,
        cmd_id=33,
        translation_key="person",
        value=lambda api, ch: api.ai_detected(ch, PERSON_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, PERSON_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=VEHICLE_DETECTION_TYPE,
        cmd_id=33,
        translation_key="vehicle",
        value=lambda api, ch: api.ai_detected(ch, VEHICLE_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, VEHICLE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PET_DETECTION_TYPE,
        cmd_id=33,
        translation_key="pet",
        value=lambda api, ch: api.ai_detected(ch, PET_DETECTION_TYPE),
        supported=lambda api, ch: (
            api.ai_supported(ch, PET_DETECTION_TYPE)
            and not api.supported(ch, "ai_animal")
        ),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PET_DETECTION_TYPE,
        cmd_id=33,
        translation_key="animal",
        value=lambda api, ch: api.ai_detected(ch, PET_DETECTION_TYPE),
        supported=lambda api, ch: api.supported(ch, "ai_animal"),
    ),
    ReolinkBinarySensorEntityDescription(
        key=PACKAGE_DETECTION_TYPE,
        cmd_id=33,
        translation_key="package",
        value=lambda api, ch: api.ai_detected(ch, PACKAGE_DETECTION_TYPE),
        supported=lambda api, ch: api.ai_supported(ch, PACKAGE_DETECTION_TYPE),
    ),
    ReolinkBinarySensorEntityDescription(
        key="visitor",
        cmd_id=33,
        translation_key="visitor",
        value=lambda api, ch: api.visitor_detected(ch),
        supported=lambda api, ch: api.is_doorbell(ch),
    ),
    ReolinkBinarySensorEntityDescription(
        key="cry",
        cmd_id=33,
        translation_key="cry",
        value=lambda api, ch: api.ai_detected(ch, "cry"),
        supported=lambda api, ch: api.ai_supported(ch, "cry"),
    ),
)

BINARY_SENSORS = (
    ReolinkBinarySensorEntityDescription(
        key="sleep",
        cmd_id=145,
        cmd_key="GetChannelstatus",
        translation_key="sleep",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda api, ch: api.sleeping(ch),
        supported=lambda api, ch: api.supported(ch, "sleep"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkBinarySensorEntity] = []
    for channel in reolink_data.host.api.channels:
        entities.extend(
            ReolinkPushBinarySensorEntity(reolink_data, channel, entity_description)
            for entity_description in BINARY_PUSH_SENSORS
            if entity_description.supported(reolink_data.host.api, channel)
        )
        entities.extend(
            ReolinkBinarySensorEntity(reolink_data, channel, entity_description)
            for entity_description in BINARY_SENSORS
            if entity_description.supported(reolink_data.host.api, channel)
        )

    async_add_entities(entities)


class ReolinkBinarySensorEntity(ReolinkChannelCoordinatorEntity, BinarySensorEntity):
    """Base binary-sensor class for Reolink IP camera."""

    entity_description: ReolinkBinarySensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

        if self._host.api.model in DUAL_LENS_DUAL_MOTION_MODELS:
            if entity_description.translation_key is not None:
                key = entity_description.translation_key
            else:
                key = entity_description.key
            self._attr_translation_key = f"{key}_lens_{self._channel}"

    @property
    def is_on(self) -> bool:
        """State of the sensor."""
        return self.entity_description.value(self._host.api, self._channel)


class ReolinkPushBinarySensorEntity(ReolinkBinarySensorEntity):
    """Binary-sensor class for Reolink IP camera motion sensors."""

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._host.unique_id}_{self._channel}",
                self._async_handle_event,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._host.unique_id}_all",
                self._async_handle_event,
            )
        )

    async def _async_handle_event(self, event: str) -> None:
        """Handle incoming event for motion detection."""
        self.async_write_ha_state()
