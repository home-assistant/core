"""Number entities for the Bang & Olufsen integration."""
from __future__ import annotations

from mozart_api.models import Bass, SoundSettings, Treble

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Number entities from config entry."""
    entities = []

    # Add Number entities.
    for number in hass.data[DOMAIN][config_entry.unique_id][EntityEnum.NUMBERS]:
        entities.append(number)

    async_add_entities(new_entities=entities)


class BangOlufsenNumber(BangOlufsenEntity, NumberEntity):
    """Base Number class."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the Number."""
        super().__init__(entry)

        self._attr_mode = NumberMode.AUTO
        self._attr_native_value = 0.0
        self._attr_entity_category = EntityCategory.CONFIG


class BangOlufsenNumberTreble(BangOlufsenNumber):
    """Treble Number."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the treble Number."""
        super().__init__(entry)

        number_range: range = range(-6, 6, 1)
        self._attr_native_min_value = float(number_range.start)
        self._attr_native_max_value = float(number_range.stop)
        self._attr_name = f"{self._name} Treble"
        self._attr_unique_id = f"{self._unique_id}-treble"
        self._attr_icon = "mdi:equalizer"
        self._attr_mode = NumberMode.SLIDER

    async def async_set_native_value(self, value: float) -> None:
        """Set the treble value."""
        self._client.set_sound_settings_adjustments_treble(
            treble=Treble(value=value), async_req=True
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
        self._attr_native_value = data.adjustments.treble
        self.async_write_ha_state()


class BangOlufsenNumberBass(BangOlufsenNumber):
    """Bass Number."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the bass Number."""
        super().__init__(entry)

        number_range: range = range(-6, 6, 1)
        self._attr_native_min_value = float(number_range.start)
        self._attr_native_max_value = float(number_range.stop)
        self._attr_name = f"{self._name} Bass"
        self._attr_unique_id = f"{self._unique_id}-bass"
        self._attr_icon = "mdi:equalizer"
        self._attr_mode = NumberMode.SLIDER

    async def async_set_native_value(self, value: float) -> None:
        """Set the bass value."""
        self._client.set_sound_settings_adjustments_bass(
            bass=Bass(value=value), async_req=True
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
        self._attr_native_value = data.adjustments.bass
        self.async_write_ha_state()
