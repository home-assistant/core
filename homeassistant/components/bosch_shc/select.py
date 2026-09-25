"""Platform for select integration."""

from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from boschshcpy import OutdoorSirenService, SHCOutdoorSiren
from boschshcpy.device import SHCDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCSelectEntityDescription[_DeviceT: SHCDevice](SelectEntityDescription):
    """Describes a SHC select entity."""

    unique_id_suffix: str
    current_option_fn: Callable[[_DeviceT, Sequence[str] | None], str | None]
    select_option_fn: Callable[[_DeviceT, str], Coroutine[Any, Any, None]]


def _siren_current_option(
    device: SHCOutdoorSiren, options: Sequence[str] | None
) -> str | None:
    """Read the Outdoor Siren's current sound level (already lowercased)."""
    try:
        return str(device.siren.sound_level.name.lower())
    except AttributeError, ValueError:
        return None


async def _siren_select_option(device: SHCOutdoorSiren, option: str) -> None:
    """Write the Outdoor Siren's sound level."""
    level = OutdoorSirenService.SoundLevel[option.upper()]
    await device.siren.async_set_configuration(sound_level=level)


SIREN_SOUND_LEVEL = "siren_sound_level"
_SIREN_SOUND_LEVEL_OPTIONS = ["low", "medium", "high"]

SELECT_TYPES: dict[str, SHCSelectEntityDescription] = {
    SIREN_SOUND_LEVEL: SHCSelectEntityDescription[SHCOutdoorSiren](
        key=SIREN_SOUND_LEVEL,
        translation_key=SIREN_SOUND_LEVEL,
        entity_category=EntityCategory.CONFIG,
        options=_SIREN_SOUND_LEVEL_OPTIONS,
        unique_id_suffix="sound_level",
        current_option_fn=_siren_current_option,
        select_option_fn=_siren_select_option,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC select platform."""
    session = config_entry.runtime_data
    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        SHCSelect(
            hass=hass,
            device=siren,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SELECT_TYPES[SIREN_SOUND_LEVEL],
        )
        for siren in session.device_helper.outdoor_sirens
        if siren.siren is not None
    )


class SHCSelect[_DeviceT: SHCDevice](SHCEntity, SelectEntity):
    """Generic SHC select entity, driven by a SHCSelectEntityDescription.

    ``current_option``/``async_select_option`` delegate to the description's
    ``current_option_fn``/``select_option_fn``, so a single class covers
    every select type — the per-type behavior lives in the description.
    """

    entity_description: SHCSelectEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCSelectEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the select entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.unique_id_suffix}"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.current_option_fn(self._device, self.options)

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option, writing it to the device."""
        await self.entity_description.select_option_fn(self._device, option)
