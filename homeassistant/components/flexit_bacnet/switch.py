"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FlexitCoordinator
from .const import DOMAIN
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Flexit switch entity."""

    is_on_fn: Callable[[FlexitBACnet], bool]
    turn_on_fn: Callable[[FlexitBACnet], Awaitable[None]]
    turn_off_fn: Callable[[FlexitBACnet], Awaitable[None]]


SWITCHES: tuple[FlexitSwitchEntityDescription, ...] = (
    FlexitSwitchEntityDescription(
        key="electric_heater",
        translation_key="electric_heater",
        is_on_fn=lambda data: data.electric_heater,
        turn_on_fn=lambda data: data.enable_electric_heater(),
        turn_off_fn=lambda data: data.disable_electric_heater(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) switch from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FlexitSwitch(coordinator, description) for description in SWITCHES
    )


class FlexitSwitch(FlexitEntity, SwitchEntity):
    """Representation of a Flexit Switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    entity_description: FlexitSwitchEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitSwitchEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) switch."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return value of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn electric heater on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.data)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn electric heater off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.data)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()
