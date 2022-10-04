"""Support for controlling projector via the PJLink protocol."""

from __future__ import annotations

from typing import Any

from pypjlink import MUTE_AUDIO

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TO_PROPERTY, DOMAIN
from .coordinator import PJLinkUpdateCoordinator
from .entity import PJLinkEntity

PJLINK_MEDIA_PLAYER = MediaPlayerEntityDescription(
    key="projector",
    entity_category=entity.EntityCategory.CONFIG,
    device_class=MediaPlayerDeviceClass.TV,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PJLink from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: PJLinkUpdateCoordinator = domain_data[entry.entry_id]

    async_add_entities([PJLinkMediaPlayerEntity(coordinator=coordinator)])


class PJLinkMediaPlayerEntity(PJLinkEntity, MediaPlayerEntity):
    """Representation of a PJLink device."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    _attr_projector_state: str | None = None
    _attr_other_info: str | None = None

    def __init__(self, coordinator: PJLinkUpdateCoordinator) -> None:
        """Initialize the PJLink device."""
        super().__init__(coordinator)

        self.entity_description = PJLINK_MEDIA_PLAYER
        self._attr_name = self.device.name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""

        pwstate = self.device.async_get_state()

        self._attr_state = STATE_ON if pwstate in ("on", "warm-up") else STATE_OFF
        self._attr_is_volume_muted = self.device.async_get_muted()
        self._attr_source = self.device.async_get_current_source()
        self._attr_source_list = self.device.source_list

        self._attr_projector_state = pwstate
        self._attr_other_info = self.device.async_get_other_info()

    def turn_off(self) -> None:
        """Turn projector off."""
        with self.device.get_projector() as projector:
            projector.set_power("off")

    def turn_on(self) -> None:
        """Turn projector on."""
        with self.device.get_projector() as projector:
            projector.set_power("on")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) of unmute (false) media player."""
        with self.device.get_projector() as projector:
            projector.set_mute(MUTE_AUDIO, mute)

    def select_source(self, source: str) -> None:
        """Set the input source."""
        proj_source = self.device.get_source_for_name(source)

        with self.device.get_projector() as projector:
            projector.set_input(*proj_source)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add the extra projector specific attributes."""
        state_attr = {}

        for attr in ATTR_TO_PROPERTY:
            if (value := getattr(self, attr)) is not None:
                state_attr[attr] = value

        return state_attr

    @property
    def projector_status(self) -> str | None:
        """Return the warming/on/cooling/off state of the device."""
        return self._attr_projector_state

    @property
    def other_info(self) -> str | None:
        """Return other information."""
        return self._attr_other_info
