"""EBUS sensors."""
import logging

from pyebus import get_icon
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import HomeAssistantType

from . import EbusFieldEntity
from .const import API, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up the EBUS component."""

    api = hass.data[DOMAIN][config_entry.entry_id][API]

    entities = []
    for msgdef in api.msgdefs:
        if msgdef.read or msgdef.update:
            for fielddef in msgdef.fields:
                entities += [EbusSensor(api, fielddef)]
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        "set_value",
        {
            vol.Required("value"): str,
        },
        "async_set_value",
    )


class EbusSensor(EbusFieldEntity):
    """EBUS Sensor."""

    @property
    def available(self):
        """Return the available."""
        return self._api.get_available(self._fielddef)

    @property
    def state(self):
        """Return the state."""
        return self._api.get_state(self._fielddef)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return get_icon(self._fielddef, self.state)

    async def async_set_value(self, **kwargs):
        """Set Value."""
        await self._api.async_set_field(self._fielddef, kwargs["value"])
