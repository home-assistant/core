"""Arcam sensors for incoming stream info."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.state import State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfFrequency
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ArcamFmjConfigEntry
from .const import (
    DOMAIN,
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ArcamFmjSensorEntityDescription(SensorEntityDescription):
    """Describes an Arcam FMJ sensor entity."""

    value_fn: Callable[[State], int | float | str | None]


SENSORS: tuple[ArcamFmjSensorEntityDescription, ...] = (
    ArcamFmjSensorEntityDescription(
        key="incoming_video_horizontal_resolution",
        translation_key="incoming_video_horizontal_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "horizontal_resolution", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_vertical_resolution",
        translation_key="incoming_video_vertical_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "vertical_resolution", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_refresh_rate",
        translation_key="incoming_video_refresh_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "refresh_rate", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_aspect_ratio",
        translation_key="incoming_video_aspect_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            getattr(state.get_incoming_video_parameters(), "aspect_ratio", None),
            "name",
            None,
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_colorspace",
        translation_key="incoming_video_colorspace",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            getattr(state.get_incoming_video_parameters(), "colorspace", None),
            "name",
            None,
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_format",
        translation_key="incoming_audio_format",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            state.get_incoming_audio_format()[0], "name", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_config",
        translation_key="incoming_audio_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            state.get_incoming_audio_format()[1], "name", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_sample_rate",
        translation_key="incoming_audio_sample_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda state: state.get_incoming_audio_sample_rate(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ sensors from a config entry."""
    client = config_entry.runtime_data
    uuid = config_entry.unique_id or config_entry.entry_id
    device_info = DeviceInfo(
        identifiers={(DOMAIN, uuid)},
        manufacturer="Arcam",
        model="Arcam FMJ AVR",
        name=config_entry.title,
    )

    entities: list[ArcamFmjSensorEntity] = []
    for zone in (1, 2):
        state = State(client, zone)
        entities.extend(
            ArcamFmjSensorEntity(
                device_info=device_info,
                uuid=uuid,
                state=state,
                description=description,
            )
            for description in SENSORS
        )
    async_add_entities(entities)


class ArcamFmjSensorEntity(SensorEntity):
    """Representation of an Arcam FMJ sensor."""

    entity_description: ArcamFmjSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        device_info: DeviceInfo,
        uuid: str,
        state: State,
        description: ArcamFmjSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._state = state
        self._attr_unique_id = f"{uuid}-{state.zn}-{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"zone": str(state.zn)}

    async def async_added_to_hass(self) -> None:
        """Once registered, add listener for events."""
        await self._state.start()
        try:
            await self._state.update()
        except ConnectionFailed as connection:
            _LOGGER.debug("Connection lost during addition: %s", connection)

        @callback
        def _data(host: str) -> None:
            if host == self._state.client.host:
                self.async_write_ha_state()

        @callback
        def _started(host: str) -> None:
            if host == self._state.client.host:
                self._attr_available = True
                self.async_write_ha_state()

        @callback
        def _stopped(host: str) -> None:
            if host == self._state.client.host:
                self._attr_available = False
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_DATA, _data)
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_STARTED, _started)
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_STOPPED, _stopped)
        )

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._state)
