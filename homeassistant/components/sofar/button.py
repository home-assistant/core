"""Support for Sofar buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.variants import HYBRID, PV, InverterType, matches

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SofarButtonEntityDescription(ButtonEntityDescription, SofarEntityDescription):
    """Describe a Sofar button entity."""

    applies_to: InverterType
    press_fn: Callable[[SofarInverter], Awaitable[None]]
    refresh_after: bool = True


BUTTON_DESCRIPTIONS: tuple[SofarButtonEntityDescription, ...] = (
    SofarButtonEntityDescription(
        key="rtc_sync",
        component="rtc_sync",
        translation_key="rtc_sync",
        entity_category=EntityCategory.CONFIG,
        applies_to=PV | HYBRID,
        press_fn=lambda device: device.async_set_time(),
    ),
    SofarButtonEntityDescription(
        key="iv_curve_scan",
        component="state",
        translation_key="iv_curve_scan",
        entity_category=EntityCategory.CONFIG,
        applies_to=HYBRID,
        press_fn=lambda device: device.async_start_iv_curve_scan(),
        refresh_after=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus button platform."""
    runtime_data = entry.runtime_data
    inverter_type = runtime_data.readings.device.inverter_type
    async_add_entities(
        SofarButton(runtime_data, description)
        for description in BUTTON_DESCRIPTIONS
        if inverter_type is not None and matches(inverter_type, description.applies_to)
    )


class SofarButton(SofarEntity, ButtonEntity):
    """Defines a Sofar button entity."""

    entity_description: SofarButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator.device)
        if self.entity_description.refresh_after:
            await self.coordinator.async_request_refresh()
