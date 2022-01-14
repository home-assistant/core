"""The lookin integration light platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, cast

from aiolookin import Remote
from aiolookin.models import UDPCommandType, UDPEvent

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_STANDBY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)

_TYPE_TO_DEVICE_CLASS = {
    "01": MediaPlayerDeviceClass.TV,
    "02": MediaPlayerDeviceClass.RECEIVER,
}

_FUNCTION_NAME_TO_FEATURE = {
    "power": SUPPORT_TURN_OFF,
    "poweron": SUPPORT_TURN_ON,
    "poweroff": SUPPORT_TURN_OFF,
    "mute": SUPPORT_VOLUME_MUTE,
    "volup": SUPPORT_VOLUME_STEP,
    "chup": SUPPORT_NEXT_TRACK,
    "chdown": SUPPORT_PREVIOUS_TRACK,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform for lookin from a config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] not in _TYPE_TO_DEVICE_CLASS:
            continue
        uuid = remote["UUID"]

        def _wrap_async_update(
            uuid: str,
        ) -> Callable[[], Coroutine[None, Any, Remote]]:
            """Create a function to capture the uuid cell variable."""

            async def _async_update() -> Remote:
                return await lookin_data.lookin_protocol.get_remote(uuid)

            return _async_update

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{config_entry.title} {uuid}",
            update_method=_wrap_async_update(uuid),
            update_interval=timedelta(
                seconds=60
            ),  # Updates are pushed (fallback is polling)
        )
        await coordinator.async_refresh()
        device: Remote = coordinator.data

        entities.append(
            LookinMedia(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
                device_class=_TYPE_TO_DEVICE_CLASS[remote["Type"]],
                coordinator=coordinator,
            )
        )

    async_add_entities(entities)


class LookinMedia(LookinPowerEntity, MediaPlayerEntity):
    """A lookin media player."""

    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
        device_class: str,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Init the lookin media player."""
        self._attr_device_class = device_class
        self._attr_supported_features: int = 0
        self._attr_state = None
        self._attr_is_volume_muted: bool = False
        super().__init__(coordinator, uuid, device, lookin_data)
        for function_name, feature in _FUNCTION_NAME_TO_FEATURE.items():
            if function_name in self._function_names:
                self._attr_supported_features |= feature
                self._attr_name = self._remote.name
        self._async_update_from_data()

    @property
    def _remote(self) -> Remote:
        return cast(Remote, self.coordinator.data)

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self._async_send_command("volup")

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        await self._async_send_command("voldown")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._async_send_command("chdown")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_send_command("chup")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self._async_send_command("mute")
        self._attr_is_volume_muted = not self.is_volume_muted
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send_command(self._power_off_command)
        self._attr_state = STATE_STANDBY
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send_command(self._power_on_command)
        self._attr_state = STATE_ON
        self.async_write_ha_state()

    def _update_from_status(self, status: str) -> None:
        """Update media property from status.

        00F0
        0 - 0/1 on/off
        0 - sourse
        F - volume, 0 - muted, 1 - volume up, F - volume down
        0 - not used
        """
        if len(status) != 4:
            return
        state = status[0]
        mute = status[2]

        self._attr_state = STATE_ON if state == "1" else STATE_STANDBY
        self._attr_is_volume_muted = mute == "0"

    def _async_push_update(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        self._update_from_status(event.value)
        self.coordinator.async_set_updated_data(self._remote)
        self.async_write_ha_state()

    async def _async_push_update_device(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        await self.coordinator.async_refresh()
        self._attr_name = self._remote.name

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.ir,
                self._uuid,
                self._async_push_update,
            )
        )
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.data,
                self._uuid,
                self._async_push_update_device,
            )
        )

    def _async_update_from_data(self) -> None:
        """Update attrs from data."""
        self._update_from_status(self._remote.status)
