"""Switch platform for the UniFi Access integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from unifi_access_api import EmergencyStatus, UnifiAccessError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator, UnifiAccessData
from .entity import UnifiAccessHubEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class UnifiAccessSwitchEntityDescription(SwitchEntityDescription):
    """Describes a UniFi Access switch entity."""

    value_fn: Callable[[EmergencyStatus], bool]
    set_fn: Callable[[EmergencyStatus, bool], EmergencyStatus]


SWITCH_DESCRIPTIONS: tuple[UnifiAccessSwitchEntityDescription, ...] = (
    UnifiAccessSwitchEntityDescription(
        key="evacuation",
        translation_key="evacuation",
        value_fn=lambda s: s.evacuation,
        set_fn=lambda s, v: EmergencyStatus(evacuation=v, lockdown=s.lockdown),
    ),
    UnifiAccessSwitchEntityDescription(
        key="lockdown",
        translation_key="lockdown",
        value_fn=lambda s: s.lockdown,
        set_fn=lambda s, v: EmergencyStatus(evacuation=s.evacuation, lockdown=v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        UnifiAccessEmergencySwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    )


class UnifiAccessEmergencySwitch(UnifiAccessHubEntity, SwitchEntity):
    """Representation of a UniFi Access emergency switch."""

    entity_description: UnifiAccessSwitchEntityDescription

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        description: UnifiAccessSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self.entity_description.value_fn(self.coordinator.data.emergency)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_emergency(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_emergency(False)

    async def _async_set_emergency(self, value: bool) -> None:
        """Set emergency status."""
        new_status = self.entity_description.set_fn(
            self.coordinator.data.emergency, value
        )
        try:
            await self.coordinator.client.set_emergency_status(new_status)
        except UnifiAccessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="emergency_failed",
            ) from err
        # Optimistically update state; the WebSocket confirmation via
        # access.data.setting.update typically arrives ~200ms later.
        # Guard against flipping coordinator.last_update_success back to True
        # while the WebSocket is disconnected and all entities are unavailable.
        if self.coordinator.last_update_success:
            self.coordinator.async_set_updated_data(
                UnifiAccessData(
                    doors=self.coordinator.data.doors,
                    emergency=new_status,
                    door_thumbnails=self.coordinator.data.door_thumbnails,
                )
            )
