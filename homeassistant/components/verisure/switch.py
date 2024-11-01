"""Support for Verisure Smartplugs."""

from __future__ import annotations

from time import monotonic
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure alarm control panel from a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VerisureSmartplug(coordinator, serial_number)
        for serial_number in coordinator.data["smart_plugs"]
    )


class VerisureSmartplug(CoordinatorEntity[VerisureDataUpdateCoordinator], SwitchEntity):
    """Representation of a Verisure smartplug."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure device."""
        super().__init__(coordinator)
        self._attr_unique_id = serial_number

        self.serial_number = serial_number
        self._change_timestamp: float = 0
        self._state = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["smart_plugs"][self.serial_number]["device"][
            "area"
        ]
        return DeviceInfo(
            name=area,
            manufacturer="Verisure",
            model="SmartPlug",
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        if monotonic() - self._change_timestamp < 10:
            return self._state
        self._state = (
            self.coordinator.data["smart_plugs"][self.serial_number]["currentState"]
            == "ON"
        )
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["smart_plugs"]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the smartplug on."""
        await self.async_set_plug_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the smartplug off."""
        await self.async_set_plug_state(False)

    async def async_set_plug_state(self, state: bool) -> None:
        """Set smartplug state."""
        command: dict[str, str | dict[str, str]] = (
            self.coordinator.verisure.set_smartplug(self.serial_number, state)
        )
        await self.hass.async_add_executor_job(
            self.coordinator.verisure.request,
            command,
        )
        self._state = state
        self._change_timestamp = monotonic()
        await self.coordinator.async_request_refresh()
