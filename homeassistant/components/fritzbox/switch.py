"""Support for AVM FRITZ!SmartHome switch devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzboxDataUpdateCoordinator, FritzBoxDeviceEntity
from .const import CONF_COORDINATOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    coordinator: FritzboxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ]
    added_devices: list[str] = []

    @callback
    def _add_entities() -> None:
        """Add devices."""
        entities: list[FritzboxSwitch] = []
        for ain, device in coordinator.data.devices.items():
            if ain in added_devices:
                continue
            added_devices.append(ain)
            if device.has_switch:
                entities.append(FritzboxSwitch(coordinator, ain))
        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities()


class FritzboxSwitch(FritzBoxDeviceEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome switches."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.data.switch_state  # type: ignore [no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self.data.set_switch_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self.data.set_switch_state_off)
        await self.coordinator.async_refresh()
