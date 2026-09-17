"""Switch platform."""

import logging
from typing import TYPE_CHECKING, Any, override

from aioonkyo import command, status

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Channel, ChannelMutingCoordinator
from .entity import OnkyoEntity

if TYPE_CHECKING:
    from . import OnkyoConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnkyoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch platform for config entry."""

    @callback
    def async_add_channel_muting_entities(
        coordinator: ChannelMutingCoordinator,
    ) -> None:
        """Add channel muting switch entities."""
        async_add_entities(
            OnkyoChannelMutingSwitch(coordinator, channel) for channel in Channel
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_channel_muting",
            async_add_channel_muting_entities,
        )
    )


# OnkyoEntity comes first, so that its availability wins over CoordinatorEntity's.
class OnkyoChannelMutingSwitch(
    OnkyoEntity, CoordinatorEntity[ChannelMutingCoordinator], SwitchEntity
):
    """Onkyo Receiver Channel Muting Switch (one per channel)."""

    def __init__(
        self,
        coordinator: ChannelMutingCoordinator,
        channel: Channel,
    ) -> None:
        """Initialize the switch entity."""
        OnkyoEntity.__init__(self, coordinator.manager)
        CoordinatorEntity.__init__(self, coordinator)

        self._channel = channel

        identifier = coordinator.manager.info.identifier
        self._attr_translation_key = f"mute_{channel}"
        self._attr_unique_id = f"{identifier}-channel_muting-{channel}"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the channel."""
        await self.coordinator.async_send_command(
            self._channel, command.ChannelMuting.Param.ON
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the channel."""
        await self.coordinator.async_send_command(
            self._channel, command.ChannelMuting.Param.OFF
        )

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.coordinator.data.get(self._channel)
        self._attr_is_on = (
            None if value is None else value is status.ChannelMuting.Param.ON
        )
        super()._handle_coordinator_update()
