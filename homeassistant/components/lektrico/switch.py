"""Support for Lektrico charging station switches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import lektricowifi

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes the Lektrico switch entities."""

    @classmethod
    def get_is_on(cls, data: Any) -> int | None:
        """Return None."""
        return None

    @classmethod
    async def turn_on(cls, device: lektricowifi.Device, data: Any) -> bool | None:
        """Return None."""
        return None

    @classmethod
    async def turn_off(cls, device: lektricowifi.Device, data: Any) -> bool | None:
        """Return None."""
        return None


@dataclass
class RequireAuthSwitchEntityDescription(LektricoSwitchEntityDescription):
    """A class that describes the Lektrico RequireAuth Switch entity."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool:
        """Get the RequireAuth."""
        return bool(data.require_auth)

    @classmethod
    async def turn_on(cls, device: lektricowifi.Device, data: Any) -> bool:
        """Turn on the RequireAuth switch."""
        return bool(await device.set_auth(False))

    @classmethod
    async def turn_off(cls, device: lektricowifi.Device, data: Any) -> bool:
        """Turn off the RequireAuth switch."""
        return bool(await device.set_auth(True))


@dataclass
class LockSwitchEntityDescription(LektricoSwitchEntityDescription):
    """A class that describes the Lektrico Lock / Unlock Switch entity."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool:
        """Check if the reported state is LOCKED."""
        return str(data.charger_state) == "LOCKED"

    @classmethod
    async def turn_on(cls, device: lektricowifi.Device, data: Any) -> bool:
        """Lock the charger."""
        return bool(await device.set_charger_locked(True))

    @classmethod
    async def turn_off(cls, device: lektricowifi.Device, data: Any) -> bool:
        """Unlock the charger."""
        return bool(await device.set_charger_locked(False))


SENSORS: tuple[LektricoSwitchEntityDescription, ...] = (
    RequireAuthSwitchEntityDescription(
        key="authentication",
        name="Authentication",
    ),
    LockSwitchEntityDescription(
        key="locked",
        name="Lock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LektricoSwitch(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for description in SENSORS
    )


class LektricoSwitch(CoordinatorEntity, SwitchEntity):
    """The entity class for Lektrico charging stations switches."""

    entity_description: LektricoSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoSwitchEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.serial_number))},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

    @property
    def is_on(self) -> bool:
        """If the switch is currently on or off."""
        return bool(self.entity_description.get_is_on(self.coordinator.data))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on(
            self.coordinator.device, self.coordinator.data
        )
        # Refresh the coordinator because a switch changed a value.
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off(
            self.coordinator.device, self.coordinator.data
        )
        # Refresh the coordinator because a switch changed a value.
        await self.coordinator.async_refresh()
