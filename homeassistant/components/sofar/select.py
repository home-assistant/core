"""Support for Sofar selects."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from sofar_modbus import ChargerUseMode, EpsControlMode, SofarInverter

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription, async_remove_unserved_entities
from .helpers import enum_member, enum_options, option_slug

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SofarSelectEntityDescription(SelectEntityDescription, SofarEntityDescription):
    """Describe a Sofar select entity."""

    value_fn: Callable[[SofarInverter], IntEnum | None]
    write_fn: Callable[[SofarInverter, str], Awaitable[None]]


SELECT_DESCRIPTIONS: tuple[SofarSelectEntityDescription, ...] = (
    SofarSelectEntityDescription(
        key="charger_use_mode",
        component="charger",
        translation_key="charger_use_mode",
        options=enum_options(ChargerUseMode),
        value_fn=lambda device: device.charger.charger_use_mode,
        write_fn=lambda device, option: device.charger.async_write_mode(
            enum_member(ChargerUseMode, option)
        ),
    ),
    SofarSelectEntityDescription(
        key="eps_control",
        component="eps",
        translation_key="eps_control",
        options=enum_options(EpsControlMode),
        value_fn=lambda device: device.eps.eps_control,
        write_fn=lambda device, option: device.eps.async_write_control(
            enum_member(EpsControlMode, option)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar select platform."""
    async_remove_unserved_entities(hass, entry, Platform.SELECT, SELECT_DESCRIPTIONS)
    runtime_data = entry.runtime_data
    async_add_entities(
        SofarSelect(runtime_data, description)
        for description in SELECT_DESCRIPTIONS
        if description.component in runtime_data.served_components
    )


class SofarSelect(SofarEntity, SelectEntity):
    """Defines a Sofar select entity."""

    entity_description: SofarSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = self.entity_description.value_fn(self.coordinator.device)
        return option_slug(value) if value is not None else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        await self.entity_description.write_fn(self.coordinator.device, option)
        await self.coordinator.async_request_refresh()
