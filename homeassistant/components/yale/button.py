"""Support for Yale buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YaleConfigEntry
from .entity import YaleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yale lock wake buttons."""
    data = config_entry.runtime_data
    async_add_entities(YaleWakeLockButton(data, lock, "wake") for lock in data.locks)


class YaleWakeLockButton(YaleEntity, ButtonEntity):
    """Representation of an Yale lock wake button."""

    _attr_translation_key = "wake"

    async def async_press(self) -> None:
        """Wake the device."""
        await self._data.async_status_async(self._device_id, self._hyper_bridge)

    @callback
    def _update_from_data(self) -> None:
        """Nothing to update as buttons are stateless."""
