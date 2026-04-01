"""Support for AVM FRITZ!SmartHome switch devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from pyfritzhome import FritzhomeDevice
from pyfritzhome.devicetypes import FritzhomeTrigger

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_STATE_MANUAL_OPEN_WINDOW_PERIOD,
    DEFAULT_OPEN_WINDOW_PERIOD,
    DOMAIN,
)
from .coordinator import FritzboxConfigEntry
from .entity import FritzBoxDeviceEntity, FritzBoxEntity
from .model import FritzEntityDescriptionMixinBase

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
        entities = (
            [
                FritzboxSwitch(coordinator, ain)
                for ain in devices
                if coordinator.data.devices[ain].has_switch
            ]
            + [
                FritzboxSwitchSecondary(coordinator, ain, description)
                for ain in devices
                for description in SWITCH_2ND_TYPES
                if coordinator.data.devices[ain].has_thermostat
            ]
            + [FritzboxTrigger(coordinator, ain) for ain in triggers]
        )

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


@dataclass(frozen=True, kw_only=True)
class FritzSwitchSecondaryEntityDescription(
    SwitchEntityDescription, FritzEntityDescriptionMixinBase
):
    """Description for Fritz!Smarthome devices with secondary switch functions."""

    is_on: Callable[[FritzhomeDevice], bool]
    turn_on: Callable[[FritzhomeDevice], None]
    turn_off: Callable[[FritzhomeDevice], None]


SWITCH_2ND_TYPES: Final[tuple[FritzSwitchSecondaryEntityDescription, ...]] = (
    FritzSwitchSecondaryEntityDescription(
        key="open_window_switch",
        translation_key="open_window_switch",
        suitable=lambda device: device.has_thermostat,
        is_on=lambda device: device.window_open,
        turn_on=lambda device: device.set_window_open(
            getattr(
                device, ATTR_STATE_MANUAL_OPEN_WINDOW_PERIOD, DEFAULT_OPEN_WINDOW_PERIOD
            ),
            True,
        ),
        turn_off=lambda device: device.set_window_open(0.0, True),
    ),
)


class FritzboxSwitchSecondary(FritzBoxDeviceEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome devices with secondary switch functions."""

    entity_description: FritzSwitchSecondaryEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state of the secondary switch function."""
        return self.entity_description.is_on(self.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the secondary switch function on."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_on, self.data
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the secondary switch function off."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_off, self.data
        )
        await self.coordinator.async_refresh()


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
