"""Support for AVM FRITZ!SmartHome switch devices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxDeviceEntity
from .const import DOMAIN
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            FritzboxSwitch(coordinator, ain)
            for ain in devices
            if coordinator.data.devices[ain].has_switch
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


class FritzboxSwitch(FritzBoxDeviceEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome switches."""

    def __init__(
        self,
        coordinator: FritzboxDataUpdateCoordinator,
        ain: str,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize the switch."""
        self.current_switch_state = False
        self.last_switch_time: datetime

        super().__init__(coordinator, ain, entity_description)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""

        # recognize if the physical switch is turned on or off
        # we need to check time difference because of laziness of the fritzbox api
        if self.last_switch_time:
            time_diff = datetime.now() - self.last_switch_time
            if (
                time_diff >= timedelta(seconds=30)
                and self.current_switch_state != self.data.switch_state
            ):
                self.current_switch_state = self.data.switch_state

        return self.current_switch_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.check_lock_state()

        await self.hass.async_add_executor_job(self.data.set_switch_state_on)

        # The switch state is not updated immediately after the switch is turned on.
        # Therefore, we need to update the switch state manually.
        self.current_switch_state = True
        self.last_switch_time = datetime.now()

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.check_lock_state()

        await self.hass.async_add_executor_job(self.data.set_switch_state_off)

        # The switch state is not updated immediately after the switch is turned on.
        # Therefore, we need to update the switch state manually.
        self.current_switch_state = False
        self.last_switch_time = datetime.now()

        await self.coordinator.async_refresh()

    def check_lock_state(self) -> None:
        """Raise an Error if manual switching via FRITZ!Box user interface is disabled."""
        if self.data.lock:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="manual_switching_disabled",
            )
