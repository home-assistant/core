"""Number platform for Lyngdorf integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lyngdorf.device import Receiver

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfSoundPressure, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LyngdorfNumberEntityDescription(NumberEntityDescription):
    """Describe a Lyngdorf number entity."""

    value_fn: Callable[[Receiver], float | None]
    set_value_fn: Callable[[Receiver, float], None]


def _set_lipsync(receiver: Receiver, value: float) -> None:
    receiver.lipsync = int(value)


def _set_trim_bass(receiver: Receiver, value: float) -> None:
    receiver.trim_bass = value


def _set_trim_centre(receiver: Receiver, value: float) -> None:
    receiver.trim_centre = value


def _set_trim_height(receiver: Receiver, value: float) -> None:
    receiver.trim_height = value


def _set_trim_lfe(receiver: Receiver, value: float) -> None:
    receiver.trim_lfe = value


def _set_trim_surround(receiver: Receiver, value: float) -> None:
    receiver.trim_surround = value


def _set_trim_treble(receiver: Receiver, value: float) -> None:
    receiver.trim_treble = value


NUMBER_ENTITIES: tuple[LyngdorfNumberEntityDescription, ...] = (
    LyngdorfNumberEntityDescription(
        key="lipsync",
        translation_key="lipsync",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        native_min_value=0,
        native_max_value=200,
        native_step=1,
        value_fn=lambda r: float(r.lipsync) if r.lipsync is not None else None,
        set_value_fn=_set_lipsync,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_bass",
        translation_key="trim_bass",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-12.0,
        native_max_value=12.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_bass,
        set_value_fn=_set_trim_bass,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_treble",
        translation_key="trim_treble",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-12.0,
        native_max_value=12.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_treble,
        set_value_fn=_set_trim_treble,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_centre",
        translation_key="trim_centre",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-10.0,
        native_max_value=10.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_centre,
        set_value_fn=_set_trim_centre,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_height",
        translation_key="trim_height",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-10.0,
        native_max_value=10.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_height,
        set_value_fn=_set_trim_height,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_lfe",
        translation_key="trim_lfe",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-10.0,
        native_max_value=10.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_lfe,
        set_value_fn=_set_trim_lfe,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_surround",
        translation_key="trim_surround",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        native_min_value=-10.0,
        native_max_value=10.0,
        native_step=0.5,
        value_fn=lambda r: r.trim_surround,
        set_value_fn=_set_trim_surround,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf number entities from a config entry."""
    receiver = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    async_add_entities(
        LyngdorfNumber(receiver, config_entry, device_info, description)
        for description in NUMBER_ENTITIES
    )


class LyngdorfNumber(LyngdorfEntity, NumberEntity):
    """Lyngdorf number entity."""

    entity_description: LyngdorfNumberEntityDescription

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(receiver)
        assert config_entry.unique_id
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._receiver)

    def set_native_value(self, value: float) -> None:
        """Set the value."""
        self.entity_description.set_value_fn(self._receiver, value)
