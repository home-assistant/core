"""Support for Sofar selects."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.enums import ChargerUseMode, EpsControlMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 1


def _enum_options(enum_type: type[IntEnum]) -> list[str]:
    """The select options a device enum maps to."""
    return [member.name.lower() for member in enum_type]


@dataclass(frozen=True, kw_only=True)
class SofarSelectEntityDescription(SelectEntityDescription, SofarEntityDescription):
    """Describe a Sofar select entity."""

    options_enum: type[IntEnum]
    write_fn: Callable[[SofarInverter, int], Awaitable[None]]


SELECT_DESCRIPTIONS: tuple[SofarSelectEntityDescription, ...] = (
    SofarSelectEntityDescription(
        key="charger_use_mode",
        component="charger",
        translation_key="charger_use_mode",
        options=_enum_options(ChargerUseMode),
        options_enum=ChargerUseMode,
        write_fn=lambda device, value: device.charger.write("charger_use_mode", value),
    ),
    SofarSelectEntityDescription(
        key="eps_control",
        component="eps",
        translation_key="eps_control",
        options=_enum_options(EpsControlMode),
        options_enum=EpsControlMode,
        write_fn=lambda device, value: device.eps.async_write_control(
            EpsControlMode(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus select platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components
    async_add_entities(
        SofarSelect(runtime_data, description)
        for description in SELECT_DESCRIPTIONS
        if description.component in served
    )


class SofarSelect(SofarEntity, SelectEntity):
    """Defines a Sofar select entity."""

    entity_description: SofarSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        value: IntEnum | None = getattr(component, self.entity_description.key)
        return value.name.lower() if value is not None else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        value = self.entity_description.options_enum[option.upper()]
        await self.entity_description.write_fn(self.coordinator.device, value.value)
        await self.coordinator.async_request_refresh()
