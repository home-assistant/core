"""Number platform for Lyngdorf integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from lyngdorf.device import Receiver
from lyngdorf.models.base import NumericRange

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfSoundPressure, UnitOfTime
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
    range_fn: Callable[[Receiver], NumericRange | None]


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
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: float(r.lipsync) if r.lipsync is not None else None,
        set_value_fn=_set_lipsync,
        range_fn=lambda r: r.lipsync_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_bass",
        translation_key="trim_bass",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_bass,
        set_value_fn=_set_trim_bass,
        range_fn=lambda r: r.trim_bass_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_treble",
        translation_key="trim_treble",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_treble,
        set_value_fn=_set_trim_treble,
        range_fn=lambda r: r.trim_treble_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_centre",
        translation_key="trim_centre",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_centre,
        set_value_fn=_set_trim_centre,
        range_fn=lambda r: r.trim_centre_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_height",
        translation_key="trim_height",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_height,
        set_value_fn=_set_trim_height,
        range_fn=lambda r: r.trim_height_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_lfe",
        translation_key="trim_lfe",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_lfe,
        set_value_fn=_set_trim_lfe,
        range_fn=lambda r: r.trim_lfe_range,
    ),
    LyngdorfNumberEntityDescription(
        key="trim_surround",
        translation_key="trim_surround",
        device_class=NumberDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda r: r.trim_surround,
        set_value_fn=_set_trim_surround,
        range_fn=lambda r: r.trim_surround_range,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf number entities from a config entry."""
    runtime_data = config_entry.runtime_data
    receiver = runtime_data.receiver

    # A None range means the model has no such control at all.
    async_add_entities(
        LyngdorfNumber(receiver, config_entry, runtime_data.device_info, description)
        for description in NUMBER_ENTITIES
        if description.range_fn(receiver) is not None
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
        super().__init__(receiver, device_info)
        assert config_entry.unique_id
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def _range(self) -> NumericRange:
        """Return the device's range for this setting."""
        range_ = self.entity_description.range_fn(self._receiver)
        # Entities are only created for controls the model actually has.
        assert range_ is not None
        return range_

    @override
    @property
    def native_min_value(self) -> float:
        """Return the minimum value the device accepts."""
        return self._range.min

    @override
    @property
    def native_max_value(self) -> float:
        """Return the maximum value the device accepts."""
        return self._range.max

    @override
    @property
    def native_step(self) -> float:
        """Return the step the device resolves."""
        return self._range.step

    @override
    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._receiver)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value.

        Async so the library's write lands on the event loop: it enqueues
        onto an asyncio primitive, which is not safe from an executor thread.
        """
        self.entity_description.set_value_fn(self._receiver, value)
