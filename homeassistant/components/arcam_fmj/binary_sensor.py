"""Arcam binary sensors."""

from arcam.fmj.state import State

from homeassistant.components.binary_sensor import BinarySensorEntity
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

    entities: list[BinarySensorEntity] = []

    for zn in (1, 2):
        zone = State(client, zn)
        entities.append(IncomingVideoInterlacedBinarySensor(device_info, zone, uuid))

    async_add_entities(entities)


class IncomingVideoInterlacedBinarySensor(BinarySensorEntity):
    """Metadata sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize sensor."""
        self._state = state
        self._attr_name = f"Zone {state.zn} Incoming Video Interlaced"
        self._attr_unique_id = f"{uuid}-{state.zn}-incoming-video-interlaced"
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Sensor value."""
        return getattr(self._state.get_incoming_video_parameters(), "interlaced", None)
