"""Support for Mikrotik routers switches."""

from dataclasses import dataclass
from typing import Any, Final, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry, mikrotik_config_entry_errors
from .entity import MikrotikDeviceEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MikrotikSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Mikrotik switch entities."""

    admin_only: bool = False


SENSORS: Final = (
    MikrotikSwitchEntityDescription(
        key="ether",
        translation_key="ether",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        admin_only=True,
    ),
    MikrotikSwitchEntityDescription(
        key="wlan",
        translation_key="wlan",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        admin_only=True,
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

    entity_description: MikrotikSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return not self._interface.get("disabled")

    async def _async_check_admin(self) -> None:
        """Raise if the switch is being operated by a non-admin user."""
        context = self.async_get_recent_context()
        if context is None or context.user_id is None:
            return
        user = await self.hass.auth.async_get_user(context.user_id)
        if user is None or not user.is_admin:
            raise Unauthorized(context=context)

    async def _set_state(self, action: str) -> None:
        """Toggle the state of the switch."""
        if self.entity_description.admin_only:
            await self._async_check_admin()

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
