"""Support for Big Ass Fans SenseME switch."""
from __future__ import annotations

from typing import Any

from aiosenseme import SensemeFan

from homeassistant import config_entries
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SensemeEntity

FAN_SWITCHS = [
    # Turning on sleep mode will disable Whoosh
    SwitchEntityDescription(
        key="sleep_mode",
        name="Sleep Mode",
    ),
    SwitchEntityDescription(
        key="motion_fan_auto",
        name="Motion",
    ),
]

FAN_LIGHT_SWITCHES = [
    SwitchEntityDescription(
        key="motion_light_auto",
        name="Light Motion",
    ),
]

LIGHT_SWITCHES = [
    SwitchEntityDescription(
        key="sleep_mode",
        name="Sleep Mode",
    ),
    SwitchEntityDescription(
        key="motion_light_auto",
        name="Motion",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    device = hass.data[DOMAIN][entry.entry_id]
    descriptions: list[SwitchEntityDescription] = []

    if device.is_fan:
        descriptions.extend(FAN_SWITCHS)
        if device.has_light:
            descriptions.extend(FAN_LIGHT_SWITCHES)
    elif device.is_light:
        descriptions.extend(LIGHT_SWITCHES)

    async_add_entities(
        [HASensemeSwitch(device, description) for description in descriptions]
    )


class HASensemeSwitch(SensemeEntity, SwitchEntity):
    """SenseME switch component."""

    def __init__(
        self, device: SensemeFan, description: SwitchEntityDescription
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_device_class = SwitchDeviceClass.SWITCH
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.uuid}-SWITCH-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = getattr(self._device, self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        setattr(self._device, self.entity_description.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        setattr(self._device, self.entity_description.key, False)
