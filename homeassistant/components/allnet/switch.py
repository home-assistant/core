"""Switch platform for ALLNET."""

from typing import Any

from allnet.exceptions import AllnetCommandError
from allnet.models import ChannelKind

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AllnetConfigEntry
from .coordinator import AllnetDataUpdateCoordinator
from .entity import AllnetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllnetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ALLNET switches."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    device_info = runtime.ha_device_info
    device_unique_id = entry.unique_id or entry.entry_id

    known_ids: set[str] = set()

    def _check_new_entities() -> None:
        new_entities: list[AllnetSwitchEntity] = []
        for channel in coordinator.data.values():
            if channel.kind != ChannelKind.SWITCH:
                continue
            if channel.id in known_ids:
                continue
            known_ids.add(channel.id)
            unique_id = f"{device_unique_id}_{channel.id}_switch"
            new_entities.append(
                AllnetSwitchEntity(
                    coordinator=coordinator,
                    channel_id=channel.id,
                    device_info=device_info,
                    unique_id=unique_id,
                    name=channel.name,
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    _check_new_entities()

    entry.async_on_unload(coordinator.async_add_listener(_check_new_entities))


class AllnetSwitchEntity(AllnetEntity, SwitchEntity):
    """Representation of an ALLNET switch channel (digital output / relay)."""

    def __init__(
        self,
        coordinator: AllnetDataUpdateCoordinator,
        channel_id: str,
        device_info: Any,
        unique_id: str,
        name: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, channel_id, device_info)
        self._attr_unique_id = unique_id
        self._attr_name = name

    @property
    def is_on(self) -> bool | None:
        """Return True when the switch is on."""
        channel = self.coordinator.data.get(self._channel_id)
        if channel is None or channel.value is None:
            return None
        return bool(channel.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Send a set-state command and refresh coordinator data."""
        try:
            await self.coordinator.client.async_set_channel_state(
                self._channel_id, state
            )
        except AllnetCommandError as err:
            raise HomeAssistantError(
                f"Failed to {'turn on' if state else 'turn off'} {self.name}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
