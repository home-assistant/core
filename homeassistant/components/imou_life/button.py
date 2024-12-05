import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ImouEntity
from .const import DOMAIN
from pyimouapi.exceptions import ImouException

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    imou_coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in imou_coordinator.devices:
        for button in device.buttons:
            entities.append(ImouButton(imou_coordinator, entry, button, device))
    async_add_entities(entities)


class ImouButton(ImouEntity, ButtonEntity):
    """imou button"""

    async def async_press(self) -> None:
        try:
            await self.coordinator.device_manager.async_press_button(self._device.device_id, self._device.channel_id,
                                                                     self._entity_type)
        except ImouException as e:
            raise HomeAssistantError(e.message)
