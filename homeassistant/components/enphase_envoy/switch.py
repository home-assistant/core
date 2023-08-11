"""Switch platform for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pyenphase import Envoy, EnvoyEnpower

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnvoyEnpowerRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEnpower], bool]
    turn_on_fn: Callable[[Envoy], Coroutine[Any, Any, dict[str, Any]]]
    turn_off_fn: Callable[[Envoy], Coroutine[Any, Any, dict[str, Any]]]


@dataclass
class EnvoyEnpowerSwitchEntityDescription(
    SwitchEntityDescription, EnvoyEnpowerRequiredKeysMixin
):
    """Describes an Envoy Enpower binary sensor entity."""


ENPOWER_GRID_SWITCH = EnvoyEnpowerSwitchEntityDescription(
    key="mains_admin_state",
    translation_key="grid_enabled",
    value_fn=lambda enpower: enpower.mains_admin_state == "closed",
    turn_on_fn=lambda envoy: envoy.go_on_grid(),
    turn_off_fn=lambda envoy: envoy.go_off_grid(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy binary sensor platform."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    envoy_serial_num = config_entry.unique_id
    assert envoy_serial_num is not None
    entities: list[SwitchEntity] = []
    if envoy_data.enpower:
        entities.extend(
            [
                EnvoyEnpowerSwitchEntity(
                    coordinator, ENPOWER_GRID_SWITCH, envoy_data.enpower
                )
            ]
        )
    async_add_entities(entities)


class EnvoyEnpowerSwitchEntity(EnvoyBaseEntity, SwitchEntity):
    """Representation of an Enphase Enpower switch entity."""

    entity_description: EnvoyEnpowerSwitchEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnpowerSwitchEntityDescription,
        enpower: EnvoyEnpower,
    ) -> None:
        """Initialize the Enphase Enpower switch entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        self.enpower = enpower
        self._serial_number = enpower.serial_number
        self._attr_unique_id = f"{self._serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            manufacturer="Enphase",
            model="Enpower",
            name=f"Enpower {self._serial_number}",
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the Enpower switch."""
        enpower = self.data.enpower
        assert enpower is not None
        return self.entity_description.value_fn(enpower)

    async def async_turn_on(self):
        """Turn on the Enpower switch."""
        await self.entity_description.turn_on_fn(self.envoy)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn off the Enpower switch."""
        await self.entity_description.turn_off_fn(self.envoy)
        await self.coordinator.async_request_refresh()
