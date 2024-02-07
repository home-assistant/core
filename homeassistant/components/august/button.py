"""Support for August buttons."""
from yalexs.lock import Lock

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AugustData
from .const import DOMAIN
from .entity import AugustEntityMixin


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up August lock wake buttons."""
    data: AugustData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(AugustWakeLockButton(data, lock) for lock in data.locks)


class AugustWakeLockButton(AugustEntityMixin, ButtonEntity):
    """Representation of an August lock wake button."""

    _attr_translation_key = "wake"

    def __init__(self, data: AugustData, device: Lock) -> None:
        """Initialize the lock wake button."""
        super().__init__(data, device)
        self._attr_unique_id = f"{self._device_id}_wake"

    async def async_press(self) -> None:
        """Wake the device."""
        await self._data.async_status_async(self._device_id, self._hyper_bridge)

    @callback
    def _update_from_data(self) -> None:
        """Nothing to update as buttons are stateless."""
