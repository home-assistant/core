import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ImouEntity
from .const import DOMAIN, PARAM_OPTIONS, PARAM_CURRENT_OPTION
from pyimouapi.exceptions import ImouException

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    _LOGGER.info("ImouSelect.async_setup_entry")
    imou_coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in imou_coordinator.devices:
        for select in device.selects.keys():
            entities.append(ImouSelect(imou_coordinator, entry, select, device))
    async_add_entities(entities)


class ImouSelect(ImouEntity, SelectEntity):
    """imou select"""

    @property
    def options(self) -> list[str]:
        return self._device.selects[self._entity_type][PARAM_OPTIONS]

    @property
    def current_option(self) -> str | None:
        return self._device.selects[self._entity_type][PARAM_CURRENT_OPTION]

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.device_manager.async_select_option(self._device, self._entity_type, option)
            self._device.selects[self._entity_type][PARAM_CURRENT_OPTION] = option
            self.async_write_ha_state()
        except ImouException as e:
            raise HomeAssistantError(e.message)
