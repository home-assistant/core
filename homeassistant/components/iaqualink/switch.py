"""Support for Aqualink pool feature switches."""

from typing import Any

from iaqualink.device import (
    AqualinkDevice,
    AqualinkLight,
    AqualinkSwitch,
    AqualinkThermostat,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AqualinkConfigEntry, refresh_system
from .coordinator import AqualinkDataUpdateCoordinator
from .entity import AqualinkEntity
from .utils import await_or_reraise

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AqualinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered switches."""
    for coordinator in config_entry.runtime_data.coordinators.values():

        def _async_add_new_devices(
            devices: list[AqualinkDevice],
            _coordinator: AqualinkDataUpdateCoordinator = coordinator,
        ) -> None:
            async_add_entities(
                HassAqualinkSwitch(_coordinator, dev)
                for dev in devices
                if isinstance(dev, AqualinkSwitch)
                and not isinstance(dev, (AqualinkThermostat, AqualinkLight))
            )

        coordinator.new_device_callbacks.append(_async_add_new_devices)
        _async_add_new_devices(list(coordinator.data.values()))


class HassAqualinkSwitch(AqualinkEntity[AqualinkSwitch], SwitchEntity):
    """Representation of a switch."""

    def __init__(
        self, coordinator: AqualinkDataUpdateCoordinator, dev: AqualinkSwitch
    ) -> None:
        """Initialize AquaLink switch."""
        super().__init__(coordinator, dev)
        name = dev.label
        if name == "Cleaner":
            self._attr_icon = "mdi:robot-vacuum"
        elif name == "Waterfall" or name.endswith("Dscnt"):
            self._attr_icon = "mdi:fountain"
        elif name.endswith(("Pump", "Blower")):
            self._attr_icon = "mdi:fan"
        if name.endswith("Heater"):
            self._attr_icon = "mdi:radiator"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or not."""
        return self.dev.is_on

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await await_or_reraise(
            self.hass, self.coordinator.config_entry, self.dev.turn_on()
        )

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await await_or_reraise(
            self.hass, self.coordinator.config_entry, self.dev.turn_off()
        )
