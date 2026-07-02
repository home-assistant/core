"""Switch platform for KEBA P40."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from keba_kecontact_p40 import KebaP40Error, Wallbox, WallboxState

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import KebaP40ConfigEntry, KebaP40DataUpdateCoordinator
from .entity import KebaP40Entity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class KebaP40SwitchDescription(SwitchEntityDescription):
    """Describes a KEBA P40 switch."""

    is_on_fn: Callable[[Wallbox], bool]
    on_fn: Callable[[KebaP40DataUpdateCoordinator], Awaitable[None]]
    off_fn: Callable[[KebaP40DataUpdateCoordinator], Awaitable[None]]


SWITCHES: tuple[KebaP40SwitchDescription, ...] = (
    KebaP40SwitchDescription(
        key="charging",
        translation_key="charging",
        is_on_fn=lambda wb: wb.state is WallboxState.CHARGING,
        on_fn=lambda c: c.client.start_charging(c.serial),
        off_fn=lambda c: c.client.stop_charging(c.serial),
    ),
    KebaP40SwitchDescription(
        key="available",
        translation_key="available",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda wb: wb.state is not WallboxState.UNAVAILABLE,
        on_fn=lambda c: c.client.set_availability(c.serial, True),
        off_fn=lambda c: c.client.set_availability(c.serial, False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        KebaP40Switch(coordinator, description) for description in SWITCHES
    )


class KebaP40Switch(KebaP40Entity, SwitchEntity):
    """A KEBA P40 switch."""

    entity_description: KebaP40SwitchDescription

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self.entity_description.is_on_fn(self._wallbox)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.entity_description.on_fn(self.coordinator)
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.off_fn(self.coordinator)
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()
