"""Support for Elgato switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from elgato import Elgato, ElgatoError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElgatoConfigEntry, ElgatoData, ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ElgatoSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Elgato switch entities."""

    has_fn: Callable[[ElgatoData], bool] = lambda _: True
    is_on_fn: Callable[[ElgatoData], bool | None]
    set_fn: Callable[[Elgato, bool], Awaitable[Any]]


SWITCHES = [
    ElgatoSwitchEntityDescription(
        key="bypass",
        translation_key="bypass",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda x: x.battery is not None,
        is_on_fn=lambda x: x.settings.battery.bypass if x.settings.battery else None,
        set_fn=lambda client, on: client.battery_bypass(on=on),
    ),
    ElgatoSwitchEntityDescription(
        key="energy_saving",
        translation_key="energy_saving",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda x: x.battery is not None,
        is_on_fn=lambda x: (
            x.settings.battery.energy_saving.enabled if x.settings.battery else None
        ),
        set_fn=lambda client, on: client.energy_saving(on=on),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elgato switches based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        ElgatoSwitchEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SWITCHES
        if description.has_fn(coordinator.data)
    )


class ElgatoSwitchEntity(ElgatoEntity, SwitchEntity):
    """Representation of an Elgato switch."""

    entity_description: ElgatoSwitchEntityDescription

    def __init__(
        self,
        coordinator: ElgatoDataUpdateCoordinator,
        description: ElgatoSwitchEntityDescription,
    ) -> None:
        """Initiate Elgato switch."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.info.serial_number}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.set_fn(self.coordinator.client, True)
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while updating the Elgato Light"
            ) from error
        finally:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.set_fn(self.coordinator.client, False)
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while updating the Elgato Light"
            ) from error
        finally:
            await self.coordinator.async_refresh()
