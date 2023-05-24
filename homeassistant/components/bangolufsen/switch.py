"""Switch entities for the Bang & Olufsen integration."""
from __future__ import annotations

from typing import Any

from mozart_api.models import Loudness, SoundSettings

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BangOlufsenEntity, EntityEnum, WebSocketNotification


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switches from config_entry."""
    entities = []

    # Add switch entities.
    for switch in hass.data[DOMAIN][config_entry.unique_id][EntityEnum.SWITCHES]:
        entities.append(switch)

    async_add_entities(new_entities=entities)


class BangOlufsenSwitch(BangOlufsenEntity, SwitchEntity):
    """Base Switch class."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the Switch."""
        super().__init__(entry)

        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_entity_category = EntityCategory.CONFIG


class BangOlufsenSwitchLoudness(BangOlufsenSwitch):
    """Loudness Switch."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the loudness Switch."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Loudness"
        self._attr_unique_id = f"{self._unique_id}-loudness"
        self._attr_icon = "mdi:music-note-plus"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the option."""
        self._client.set_sound_settings_adjustments_loudness(
            loudness=Loudness(value=True),
            async_req=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the option."""
        self._client.set_sound_settings_adjustments_loudness(
            loudness=Loudness(value=False),
            async_req=True,
        )

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.SOUND_SETTINGS}",
                self._update_sound_settings,
            )
        )

    async def _update_sound_settings(self, data: SoundSettings) -> None:
        """Update sound settings."""
        self._attr_is_on = data.adjustments.loudness
        self.async_write_ha_state()
