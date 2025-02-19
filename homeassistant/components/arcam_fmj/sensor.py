"""Arcam sensors."""

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

    entities: list[SensorEntity] = []
    for zn in (1, 2):
        zone = State(client, zn)
        entities.append(
            IncomingVideoResolutionHorizontalSensor(device_info, zone, uuid)
        )
        entities.append(IncomingVideoResolutionVerticalSensor(device_info, zone, uuid))
        entities.append(IncomingVideoRefreshRateSensor(device_info, zone, uuid))
        entities.append(IncomingVideoAspectRatioSensor(device_info, zone, uuid))
        entities.append(IncomingVideoColorspaceSensor(device_info, zone, uuid))
        entities.append(IncomingAudioFormatSensor(device_info, zone, uuid))
        entities.append(IncomingAudioConfigurationSensor(device_info, zone, uuid))
        entities.append(IncomingAudioSampleRateSensor(device_info, zone, uuid))

    async_add_entities(entities)


class IncomingVideoResolutionHorizontalSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Resolution, Horizontal"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-resolution-horizontal"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Sensor value."""
        return getattr(
            self._state.get_incoming_video_parameters(), "horizontal_resolution", None
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Unit of measure."""
        return "px"

    @property
    def state_class(self) -> SensorStateClass:
        """State class."""
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self) -> int:
        """Display precision."""
        return 0


class IncomingVideoResolutionVerticalSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Resolution, Vertical"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-resolution-vertical"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Sensor value."""
        return getattr(
            self._state.get_incoming_video_parameters(), "vertical_resolution", None
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Unit of measure."""
        return "px"

    @property
    def state_class(self) -> SensorStateClass:
        """State class."""
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self) -> int:
        """Display precision."""
        return 0


class IncomingVideoRefreshRateSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Refresh Rate"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-refresh-rate"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Sensor value."""
        return getattr(
            self._state.get_incoming_video_parameters(), "refresh_rate", None
        )

    @property
    def device_class(self) -> SensorDeviceClass:
        """Device class."""
        return SensorDeviceClass.FREQUENCY

    @property
    def native_unit_of_measurement(self) -> str:
        """Unit of measure."""
        return "Hz"

    @property
    def state_class(self) -> SensorStateClass:
        """State class."""
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self) -> int:
        """Display precision."""
        return 0


class IncomingVideoAspectRatioSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Aspect Ratio"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-aspect-ratio"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Sensor value."""
        return getattr(
            getattr(self._state.get_incoming_video_parameters(), "aspect_ratio", None),
            "name",
            None,
        )


class IncomingVideoColorspaceSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Colorspace"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-colorspace"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Sensor value."""
        return getattr(
            getattr(self._state.get_incoming_video_parameters(), "colorspace", None),
            "name",
            None,
        )


class IncomingAudioFormatSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Audio Format"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-audio-format"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Sensor value."""
        return getattr(self._state.get_incoming_audio_format()[0], "name", None)


class IncomingAudioConfigurationSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Audio Configuration"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-audio-configuration"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Sensor value."""
        return getattr(self._state.get_incoming_audio_format()[1], "name", None)


class IncomingAudioSampleRateSensor(SensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Audio Sample Rate"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-audio-sample-rate"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        """Sensor value."""
        return self._state.get_incoming_audio_sample_rate()

    @property
    def device_class(self) -> SensorDeviceClass:
        """Device class."""
        return SensorDeviceClass.FREQUENCY

    @property
    def native_unit_of_measurement(self) -> str:
        """Unit of measure."""
        return "Hz"

    @property
    def state_class(self) -> SensorStateClass:
        """State class."""
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self) -> int:
        """Display precision."""
        return 0
