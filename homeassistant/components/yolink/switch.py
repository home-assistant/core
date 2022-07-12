"""YoLink Switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.device import YoLinkDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COORDINATORS,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_SWITCH,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkSwitchEntityDescription(SwitchEntityDescription):
    """YoLink SwitchEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    value: Callable[[Any], bool | None] = lambda _: None
    state_key: str = "state"


DEVICE_TYPES: tuple[YoLinkSwitchEntityDescription, ...] = (
    YoLinkSwitchEntityDescription(
        key="outlet_state",
        device_class=SwitchDeviceClass.OUTLET,
        name="State",
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_OUTLET,
    ),
    YoLinkSwitchEntityDescription(
        key="manipulator_state",
        name="State",
        icon="mdi:pipe",
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MANIPULATOR,
    ),
    YoLinkSwitchEntityDescription(
        key="switch_state",
        name="State",
        device_class=SwitchDeviceClass.SWITCH,
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_SWITCH,
    ),
)

DEVICE_TYPE = [ATTR_DEVICE_MANIPULATOR, ATTR_DEVICE_OUTLET, ATTR_DEVICE_SWITCH]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink switch from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    switch_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in DEVICE_TYPE
    ]
    entities = []
    for switch_device_coordinator in switch_device_coordinators:
        for description in DEVICE_TYPES:
            if description.exists_fn(switch_device_coordinator.device):
                entities.append(
                    YoLinkSwitchEntity(
                        config_entry, switch_device_coordinator, description
                    )
                )
    async_add_entities(entities)


class YoLinkSwitchEntity(YoLinkEntity, SwitchEntity):
    """YoLink Switch Entity."""

    entity_description: YoLinkSwitchEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSwitchEntityDescription,
    ) -> None:
        """Init YoLink switch."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )
        self._attr_name = (
            f"{coordinator.device.device_name} ({self.entity_description.name})"
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self.entity_description.value(
            state.get(self.entity_description.state_key)
        )
        self.async_write_ha_state()

    async def call_state_change(self, state: str) -> None:
        """Call setState api to change switch state."""
        await self.call_device_api("setState", {"state": state})
        self._attr_is_on = self.entity_description.value(state)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_state_change("open")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.call_state_change("close")
