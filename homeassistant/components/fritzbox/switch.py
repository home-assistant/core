"""Support for AVM FRITZ!SmartHome switch devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    CONF_COORDINATOR,
    DOMAIN as FRITZBOX_DOMAIN,
)
from .model import SwitchExtraAttributes


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    entities: list[FritzboxSwitch] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if not device.has_switch:
            continue

        entities.append(
            FritzboxSwitch(
                {
                    ATTR_NAME: f"{device.name}",
                    ATTR_ENTITY_ID: f"{device.ain}",
                    ATTR_UNIT_OF_MEASUREMENT: None,
                    ATTR_DEVICE_CLASS: None,
                    ATTR_STATE_CLASS: None,
                },
                coordinator,
                ain,
            )
        )

    async_add_entities(entities)


class FritzboxSwitch(FritzBoxEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome switches."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.switch_state  # type: ignore [no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self.device.set_switch_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self.device.set_switch_state_off)
        await self.coordinator.async_refresh()

    @property
    def extra_state_attributes(self) -> SwitchExtraAttributes:
        """Return the state attributes of the device."""
        attrs: SwitchExtraAttributes = {
            ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
            ATTR_STATE_LOCKED: self.device.lock,
        }
        return attrs
