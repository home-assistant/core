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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes binary sensor entities."""

    value: Callable[[Host, int], bool]


@dataclass(frozen=True, kw_only=True)
class ReolinkSmartAIBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    ReolinkEntityDescription,
):
    """A class that describes Smart AI binary sensor entities."""

    smart_type: str
    value: Callable[[Host, int, int], bool]
    supported: Callable[[Host, int, int], bool] = lambda api, ch, loc: True


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

BINARY_SMART_AI_SENSORS = (
    ReolinkSmartAIBinarySensorEntityDescription(
        key="crossline_person",
        smart_type="crossline",
        cmd_id=33,
        translation_key="crossline_person",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "crossline", loc, "people")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_crossline")
            and "people" in api.baichuan.smart_ai_type_list(ch, "crossline", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="crossline_vehicle",
        smart_type="crossline",
        cmd_id=33,
        translation_key="crossline_vehicle",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "crossline", loc, "vehicle")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_crossline")
            and "vehicle" in api.baichuan.smart_ai_type_list(ch, "crossline", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="crossline_dog_cat",
        smart_type="crossline",
        cmd_id=33,
        translation_key="crossline_dog_cat",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "crossline", loc, "dog_cat")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_crossline")
            and "dog_cat" in api.baichuan.smart_ai_type_list(ch, "crossline", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="intrusion_person",
        smart_type="intrusion",
        cmd_id=33,
        translation_key="intrusion_person",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "intrusion", loc, "people")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_intrusion")
            and "people" in api.baichuan.smart_ai_type_list(ch, "intrusion", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="intrusion_vehicle",
        smart_type="intrusion",
        cmd_id=33,
        translation_key="intrusion_vehicle",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "intrusion", loc, "vehicle")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_intrusion")
            and "vehicle" in api.baichuan.smart_ai_type_list(ch, "intrusion", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="intrusion_dog_cat",
        smart_type="intrusion",
        cmd_id=33,
        translation_key="intrusion_dog_cat",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "intrusion", loc, "dog_cat")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_intrusion")
            and "dog_cat" in api.baichuan.smart_ai_type_list(ch, "intrusion", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="linger_person",
        smart_type="loitering",
        cmd_id=33,
        translation_key="linger_person",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "loitering", loc, "people")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_linger")
            and "people" in api.baichuan.smart_ai_type_list(ch, "loitering", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="linger_vehicle",
        smart_type="loitering",
        cmd_id=33,
        translation_key="linger_vehicle",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "loitering", loc, "vehicle")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_linger")
            and "vehicle" in api.baichuan.smart_ai_type_list(ch, "loitering", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="linger_dog_cat",
        smart_type="loitering",
        cmd_id=33,
        translation_key="linger_dog_cat",
        value=lambda api, ch, loc: (
            api.baichuan.smart_ai_state(ch, "loitering", loc, "dog_cat")
        ),
        supported=lambda api, ch, loc: (
            api.supported(ch, "ai_linger")
            and "dog_cat" in api.baichuan.smart_ai_type_list(ch, "loitering", loc)
        ),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="forgotten_item",
        smart_type="legacy",
        cmd_id=33,
        translation_key="forgotten_item",
        value=lambda api, ch, loc: (api.baichuan.smart_ai_state(ch, "legacy", loc)),
        supported=lambda api, ch, loc: api.supported(ch, "ai_forgotten_item"),
    ),
    ReolinkSmartAIBinarySensorEntityDescription(
        key="taken_item",
        smart_type="loss",
        cmd_id=33,
        translation_key="taken_item",
        value=lambda api, ch, loc: (api.baichuan.smart_ai_state(ch, "loss", loc)),
        supported=lambda api, ch, loc: api.supported(ch, "ai_taken_item"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = config_entry.runtime_data
    api = reolink_data.host.api

    entities: list[ReolinkBinarySensorEntity | ReolinkSmartAIBinarySensorEntity] = []
    for channel in api.channels:
        entities.extend(
            ReolinkPushBinarySensorEntity(reolink_data, channel, entity_description)
            for entity_description in BINARY_PUSH_SENSORS
            if entity_description.supported(api, channel)
        )
        entities.extend(
            ReolinkBinarySensorEntity(reolink_data, channel, entity_description)
            for entity_description in BINARY_SENSORS
            if entity_description.supported(api, channel)
        )
        entities.extend(
            ReolinkSmartAIBinarySensorEntity(
                reolink_data, channel, location, entity_description
            )
            for entity_description in BINARY_SMART_AI_SENSORS
            for location in api.baichuan.smart_location_list(
                channel, entity_description.key
            )
            if entity_description.supported(api, channel, location)
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


class ReolinkSmartAIBinarySensorEntity(
    ReolinkChannelCoordinatorEntity, BinarySensorEntity
):
    """Binary-sensor class for Reolink IP camera Smart AI sensors."""

    entity_description: ReolinkSmartAIBinarySensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        location: int,
        entity_description: ReolinkSmartAIBinarySensorEntityDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)
        unique_index = self._host.api.baichuan.smart_ai_index(
            channel, entity_description.smart_type, location
        )
        self._attr_unique_id = f"{self._attr_unique_id}_{unique_index}"

        self._location = location
        self._attr_translation_placeholders = {
            "zone_name": self._host.api.baichuan.smart_ai_name(
                channel, entity_description.smart_type, location
            )
        }

    @property
    def is_on(self) -> bool:
        """State of the sensor."""
        return self.entity_description.value(
            self._host.api, self._channel, self._location
        )
