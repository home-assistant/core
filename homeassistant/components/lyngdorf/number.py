"""Number platform for Lyngdorf integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf import LyngdorfReceiver, NumericControl, NumericRange, Trim

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

    # Whether the model has this control at all. Must not depend on the device
    # having reported a value, or the entity is dropped at startup.
    range_fn: Callable[[LyngdorfReceiver], NumericRange | None]
    control_fn: Callable[[LyngdorfReceiver], NumericControl | None]
    set_value_fn: Callable[[NumericControl, float], Awaitable[None]]


NUMBER_ENTITIES: tuple[LyngdorfNumberEntityDescription, ...] = (
    LyngdorfNumberEntityDescription(
        key="lipsync",
        translation_key="lipsync",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: r.lipsync_range,
        control_fn=lambda r: r.lipsync,
        # The device takes lip sync as whole milliseconds.
        set_value_fn=lambda c, v: c.set(round(v)),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_bass",
        translation_key="trim_bass",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.BASS)) else None,
        control_fn=lambda r: r.trims.get(Trim.BASS),
        set_value_fn=lambda c, v: c.set(v),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_treble",
        translation_key="trim_treble",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.TREBLE)) else None,
        control_fn=lambda r: r.trims.get(Trim.TREBLE),
        set_value_fn=lambda c, v: c.set(v),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_centre",
        translation_key="trim_centre",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.CENTER)) else None,
        control_fn=lambda r: r.trims.get(Trim.CENTER),
        set_value_fn=lambda c, v: c.set(v),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_height",
        translation_key="trim_height",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.HEIGHT)) else None,
        control_fn=lambda r: r.trims.get(Trim.HEIGHT),
        set_value_fn=lambda c, v: c.set(v),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_lfe",
        translation_key="trim_lfe",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.LFE)) else None,
        control_fn=lambda r: r.trims.get(Trim.LFE),
        set_value_fn=lambda c, v: c.set(v),
    ),
    LyngdorfNumberEntityDescription(
        key="trim_surround",
        translation_key="trim_surround",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        entity_category=EntityCategory.CONFIG,
        range_fn=lambda r: c.range if (c := r.trims.get(Trim.SURROUND)) else None,
        control_fn=lambda r: r.trims.get(Trim.SURROUND),
        set_value_fn=lambda c, v: c.set(v),
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
        receiver: LyngdorfReceiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def _range(self) -> NumericRange:
        """Return the device's range for this setting."""
        device_range = self.entity_description.range_fn(self._receiver)
        # Entities are only created for controls the model actually has.
        if TYPE_CHECKING:
            assert device_range is not None
        return device_range

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
        control = self.entity_description.control_fn(self._receiver)
        return control.value if control is not None else None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if (control := self.entity_description.control_fn(self._receiver)) is not None:
            await self.entity_description.set_value_fn(control, value)
