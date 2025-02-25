"""Arcam sensors."""

from collections.abc import Callable
import re

from arcam.fmj.state import State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ArcamFmjConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensor entry setup."""
    entities: list[SensorEntity] = []

    client = config_entry.runtime_data
    uuid = config_entry.unique_id or config_entry.entry_id
    device_info = DeviceInfo(
        identifiers={
            (DOMAIN, uuid),
        },
        manufacturer="Arcam",
        model="Arcam FMJ AVR",
        name=config_entry.title,
    )

    for zn in (1, 2):
        zone = State(client, zn)
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Video Resolution, Horizontal",
                lambda zone: getattr(
                    zone.get_incoming_video_parameters(), "horizontal_resolution", None
                ),
                SensorStateClass.MEASUREMENT,
                "px",
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Video Resolution, Vertical",
                lambda zone: getattr(
                    zone.get_incoming_video_parameters(), "vertical_resolution", None
                ),
                SensorStateClass.MEASUREMENT,
                "px",
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Video Refresh Rate",
                lambda zone: getattr(
                    zone.get_incoming_video_parameters(), "refresh_rate", None
                ),
                SensorStateClass.MEASUREMENT,
                "Hz",
                SensorDeviceClass.FREQUENCY,
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Video Aspect Ratio",
                lambda zone: getattr(
                    getattr(zone.get_incoming_video_parameters(), "aspect_ratio", None),
                    "name",
                    None,
                ),
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Video Colorspace",
                lambda zone: getattr(
                    getattr(zone.get_incoming_video_parameters(), "colorspace", None),
                    "name",
                    None,
                ),
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Audio Format",
                lambda zone: getattr(zone.get_incoming_audio_format()[0], "name", None),
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Audio Configuration",
                lambda zone: getattr(zone.get_incoming_audio_format()[1], "name", None),
            )
        )
        entities.append(
            ArcamFmjSensor(
                device_info,
                uuid,
                zone,
                "Incoming Audio Sample Rate",
                lambda zone: zone.get_incoming_audio_sample_rate(),
                SensorStateClass.MEASUREMENT,
                "Hz",
                SensorDeviceClass.FREQUENCY,
            )
        )

    async_add_entities(entities)


class ArcamFmjSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        uuid: str,
        state: State,
        name: str,
        value_f: Callable[[State], int | str | None],
        state_class: SensorStateClass | None = None,
        unit_of_measurement: str | None = None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} {name}"
        self._attr_unique_id = f"{uuid}-{state.zn}-{re.sub(r'\W+', '-', name.lower())}"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info
        self._value_f = value_f
        self._state_class = state_class
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class

    @property
    def native_value(self) -> int | str | None:
        """Sensor value."""
        return self._value_f(self._state)

    @property
    def state_class(self) -> SensorStateClass | None:
        """State class."""
        return self._state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measure."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Device class."""
        return self._device_class

    @property
    def suggested_display_precision(self) -> int:
        """Display precision."""
        return 0
