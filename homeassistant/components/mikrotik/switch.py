"""Support for Mikrotik routers switches."""

from typing import Any, Final, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry, mikrotik_config_entry_errors
from .entity import MikrotikDeviceEntity

PARALLEL_UPDATES = 0


SENSORS: Final = (
    SwitchEntityDescription(
        key="ether",
        translation_key="ether",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="wlan",
        translation_key="wlan",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mikrotik switch based on a config entry."""

    coordinator = entry.runtime_data

    switch_list = [
        MikrotikSwitchEntity(entry, coordinator, switch_desc, interface)
        for switch_desc in SENSORS
        for interface in coordinator.api.interfaces
        if interface.get("type") == switch_desc.key
    ]

    async_add_entities(switch_list)


class MikrotikSwitchEntity(MikrotikDeviceEntity, SwitchEntity):
    """Switch device."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return not self._interface.get("disabled")

    async def _set_state(self, action: str) -> None:
        """Toggle the state of the switch."""
        with mikrotik_config_entry_errors():
            await self.hass.async_add_executor_job(
                self.coordinator.api.command,
                f"/interface/{action}",
                {".id": self._interface[".id"]},
            )
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state("enable")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state("disable")
