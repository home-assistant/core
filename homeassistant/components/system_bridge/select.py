"""Support for System Bridge selects."""

from typing import override

from systembridgeconnector.models.system_control import PowerProfileRequest

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge selects based on a config entry."""
    coordinator = entry.runtime_data
    added = False

    # Only systems with power profiles report one, and the daemon providing
    # them can start after System Bridge
    @callback
    def _async_add_power_profile() -> None:
        nonlocal added
        if added or (system := coordinator.data.system) is None:
            return
        if system.power_profile is None:
            return
        added = True
        async_add_entities(
            [
                SystemBridgePowerProfileSelect(
                    coordinator, entry.data[CONF_PORT], "power_profile"
                )
            ]
        )

    _async_add_power_profile()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_power_profile))


class SystemBridgePowerProfileSelect(SystemBridgeEntity, SelectEntity):
    """Define a System Bridge power profile select."""

    _attr_translation_key = "power_profile"

    @property
    @override
    def available(self) -> bool:
        """Return True if the system reports a power profile."""
        return (
            super().available
            and (system := self.coordinator.data.system) is not None
            and system.power_profile is not None
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active power profile."""
        if (system := self.coordinator.data.system) is None:
            return None
        return system.power_profile

    @property
    @override
    def options(self) -> list[str]:
        """Return the power profiles that can be switched to."""
        if (system := self.coordinator.data.system) is None:
            return []
        return system.power_profiles

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the power profile."""
        await self._async_system_control(
            self.coordinator.websocket_client.set_power_profile(
                PowerProfileRequest(profile=option)
            )
        )
