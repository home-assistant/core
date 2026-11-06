"""Support for Sofar buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from sofar_modbus.modern.device import SofarInverter

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SofarButtonEntityDescription(ButtonEntityDescription, SofarEntityDescription):
    """Describe a Sofar button entity."""

    supported_fn: Callable[[SofarInverter], bool]
    press_fn: Callable[[SofarInverter], Awaitable[None]]
    refresh_after: bool = True


BUTTON_DESCRIPTIONS: tuple[SofarButtonEntityDescription, ...] = (
    SofarButtonEntityDescription(
        key="rtc_sync",
        component="rtc_sync",
        translation_key="rtc_sync",
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda device: device.supports_set_time,
        press_fn=lambda device: device.async_set_time(),
    ),
    SofarButtonEntityDescription(
        key="iv_curve_scan",
        component="state",
        translation_key="iv_curve_scan",
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda device: device.supports_iv_curve_scan,
        press_fn=lambda device: device.async_start_iv_curve_scan(),
        refresh_after=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar button platform."""
    runtime_data = entry.runtime_data
    added: set[str] = set()

    @callback
    def _async_add_supported() -> None:
        """Add a button the first time the inverter's type supports it."""
        new = [
            description
            for description in BUTTON_DESCRIPTIONS
            if description.key not in added
            and description.supported_fn(runtime_data.readings.device)
        ]
        if not new:
            return
        added.update(description.key for description in new)
        async_add_entities(
            SofarButton(runtime_data, description) for description in new
        )

    _async_add_supported()
    entry.async_on_unload(
        runtime_data.readings.async_add_listener(_async_add_supported)
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
