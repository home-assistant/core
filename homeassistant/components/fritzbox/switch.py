"""Support for AVM FRITZ!SmartHome switch devices."""

from __future__ import annotations

from typing import Any

from pyfritzhome.devicetypes import FritzhomeTrigger

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FritzboxConfigEntry
from .entity import FritzBoxDeviceEntity, FritzBoxEntity

# Coordinator handles data updates, so we can allow unlimited parallel updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(
        devices: set[str] | None = None, triggers: set[str] | None = None
    ) -> None:
        """Add devices and triggers."""
        if devices is None:
            devices = coordinator.new_devices
        if triggers is None:
            triggers = coordinator.new_triggers
        if not devices and not triggers:
            return
        entities = [
            FritzboxSwitch(coordinator, ain)
            for ain in devices
            if coordinator.data.devices[ain].has_switch
        ] + [FritzboxTrigger(coordinator, ain) for ain in triggers]

        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices), set(coordinator.data.triggers))


class FritzboxSwitch(FritzBoxDeviceEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome switches."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.data.switch_state  # type: ignore [no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.check_lock_state()
        await self.hass.async_add_executor_job(self.data.set_switch_state_on, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.check_lock_state()
        await self.hass.async_add_executor_job(self.data.set_switch_state_off, True)
        await self.coordinator.async_refresh()

    def check_lock_state(self) -> None:
        """Raise an Error if manual switching via FRITZ!Box user interface is disabled."""
        if self.data.lock:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="manual_switching_disabled",
            )


class FritzboxTrigger(FritzBoxEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome triggers."""

    @property
    def data(self) -> FritzhomeTrigger:
        """Return the trigger data entity."""
        return self.coordinator.data.triggers[self.ain]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name=self.data.name,
            identifiers={(DOMAIN, self.ain)},
            configuration_url=self.coordinator.configuration_url,
            manufacturer="FRITZ!",
            model="SmartHome Routine",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the trigger is active."""
        return self.data.active  # type: ignore [no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the trigger."""
        await self.hass.async_add_executor_job(
            self.coordinator.fritz.set_trigger_active, self.ain
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the trigger."""
        await self.hass.async_add_executor_job(
            self.coordinator.fritz.set_trigger_inactive, self.ain
        )
        await self.coordinator.async_refresh()
