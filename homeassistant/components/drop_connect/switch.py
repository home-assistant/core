"""Support for DROP switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    DEV_FILTER,
    DEV_HUB,
    DEV_PROTECTION_VALVE,
    DEV_SOFTENER,
    DOMAIN,
)
from .coordinator import DROPDeviceDataUpdateCoordinator
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_VALUE: dict[int | None, bool] = {0: False, 1: True}

# Switch type constants
WATER_SWITCH = "water"
BYPASS_SWITCH = "bypass"


@dataclass(kw_only=True, frozen=True)
class DROPSwitchEntityDescription(SwitchEntityDescription):
    """Describes DROP switch entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], int | None]
    set_fn: Callable[[DROPDeviceDataUpdateCoordinator, int], Awaitable[Any]]


SWITCHES: list[DROPSwitchEntityDescription] = [
    DROPSwitchEntityDescription(
        key=WATER_SWITCH,
        translation_key=WATER_SWITCH,
        value_fn=lambda device: device.drop_api.water(),
        set_fn=lambda device, value: device.set_water(value),
    ),
    DROPSwitchEntityDescription(
        key=BYPASS_SWITCH,
        translation_key=BYPASS_SWITCH,
        value_fn=lambda device: device.drop_api.bypass(),
        set_fn=lambda device, value: device.set_bypass(value),
    ),
]

# Defines which switches are used by each device type
DEVICE_SWITCHES: dict[str, list[str]] = {
    DEV_FILTER: [BYPASS_SWITCH],
    DEV_HUB: [WATER_SWITCH, BYPASS_SWITCH],
    DEV_PROTECTION_VALVE: [WATER_SWITCH],
    DEV_SOFTENER: [BYPASS_SWITCH],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP switches from config entry."""
    _LOGGER.debug(
        "Set up switch for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    if config_entry.data[CONF_DEVICE_TYPE] in DEVICE_SWITCHES:
        async_add_entities(
            DROPSwitch(hass.data[DOMAIN][config_entry.entry_id], switch)
            for switch in SWITCHES
            if switch.key in DEVICE_SWITCHES[config_entry.data[CONF_DEVICE_TYPE]]
        )


class DROPSwitch(DROPEntity, SwitchEntity):
    """Representation of a DROP switch."""

    entity_description: DROPSwitchEntityDescription

    def __init__(
        self,
        coordinator: DROPDeviceDataUpdateCoordinator,
        entity_description: DROPSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(entity_description.key, coordinator)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return SWITCH_VALUE.get(self.entity_description.value_fn(self.coordinator))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.entity_description.set_fn(self.coordinator, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.entity_description.set_fn(self.coordinator, 0)
