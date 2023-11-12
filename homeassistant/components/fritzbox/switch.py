"""Support for AVM FRITZ!SmartHome switch devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzboxDataUpdateCoordinator, FritzBoxDeviceEntity
from .const import CONF_COORDINATOR, CONF_EVENT_LISTENER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    coordinator: FritzboxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ]

    async def _add_new_devices(event: Event) -> None:
        """Add newly discovered devices."""
        async_add_entities(
            [
                FritzboxSwitch(coordinator, ain)
                for ain, device in coordinator.data.devices.items()
                if ain in event.data.get("ains", []) and device.has_switch
            ]
        )

    hass.data[DOMAIN][entry.entry_id][CONF_EVENT_LISTENER].append(
        hass.bus.async_listen(
            f"{DOMAIN}_{entry.entry_id}_new_devices", _add_new_devices
        )
    )

    async_add_entities(
        [
            FritzboxSwitch(coordinator, ain)
            for ain, device in coordinator.data.devices.items()
            if device.has_switch
        ]
    )


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
