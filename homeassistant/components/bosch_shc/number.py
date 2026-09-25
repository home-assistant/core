"""Platform for number integration."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from boschshcpy import SHCMicromoduleRelay
from boschshcpy.device import SHCDevice

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCNumberEntityDescription[_DeviceT: SHCDevice](NumberEntityDescription):
    """Describes a SHC number entity."""

    value_fn: Callable[[_DeviceT], float | None]
    set_value_fn: Callable[[_DeviceT, float], Coroutine[Any, Any, None]]


def _impulse_length_value_fn(device: SHCMicromoduleRelay) -> float | None:
    # ImpulseSwitchService.impulse_length indexes the raw state dict
    # directly, so a partial poll that omits the field raises KeyError,
    # not just AttributeError.
    try:
        raw = device.impulse_length
    except AttributeError, KeyError:
        return None
    if raw is None:
        return None
    return float(raw) / 10.0


async def _impulse_length_set_value_fn(
    device: SHCMicromoduleRelay, value: float
) -> None:
    await device.async_set_impulse_length(round(value * 10))


IMPULSE_LENGTH = "impulse_length"

NUMBER_TYPES: dict[str, SHCNumberEntityDescription] = {
    IMPULSE_LENGTH: SHCNumberEntityDescription[SHCMicromoduleRelay](
        key=IMPULSE_LENGTH,
        translation_key=IMPULSE_LENGTH,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0.1,
        native_max_value=60.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        value_fn=_impulse_length_value_fn,
        set_value_fn=_impulse_length_set_value_fn,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC number platform."""
    session = config_entry.runtime_data
    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SHCNumber] = []
    for device in session.device_helper.micromodule_impulse_relays:
        # hasattr() only swallows AttributeError; impulse_length can raise
        # KeyError on a partial poll, which would otherwise propagate out
        # of this loop and abort setup for every remaining entity.
        try:
            impulse_length = device.impulse_length
        except AttributeError:
            continue
        except KeyError:
            impulse_length = None
        if impulse_length is None:
            continue
        entities.append(
            SHCNumber(
                hass=hass,
                device=device,
                parent_id=shc_info.unique_id,
                entry_id=config_entry.entry_id,
                description=NUMBER_TYPES[IMPULSE_LENGTH],
            )
        )

    async_add_entities(entities)


class SHCNumber[_DeviceT: SHCDevice](SHCEntity, NumberEntity):
    """Generic SHC number entity, driven by a SHCNumberEntityDescription."""

    entity_description: SHCNumberEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCNumberEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._device)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value, writing it to the device."""
        await self.entity_description.set_value_fn(self._device, value)
