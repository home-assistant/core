"""EBUS sensors."""
from pyebus import get_icon
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import HomeAssistantType

from . import Api, EbusEntity, EbusFieldEntity
from .const import API, DOMAIN, SERVICE_SETVALUE


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up the EBUS component."""

    api = hass.data[DOMAIN][config_entry.entry_id][API]

    entities = [EbusStateSensor(api)]
    for msgdef in api.ebus.msgdefs:
        if msgdef.read or msgdef.update:
            for fielddef in msgdef.children:
                entities += [EbusSensor(api, fielddef)]
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SETVALUE,
        {
            vol.Required("value"): vol.Coerce(str),
        },
        "async_set_value",
    )


class EbusSensor(EbusFieldEntity):
    """EBUS Sensor."""

    @property
    def available(self):
        """Return the available."""
        return self._api.monitor.is_field_available(self._fielddef)

    @property
    def state(self):
        """Return the state."""
        return self._api.monitor.get_field_state(self._fielddef)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return get_icon(self._fielddef, self.state)

    async def async_set_value(self, **kwargs):
        """Set Value."""
        await self._api.async_set_field(self._fielddef, kwargs["value"])

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(self._api.subscribe(self, self._fielddef))


class EbusStateSensor(EbusEntity):
    """EBUS State Sensor."""

    def __init__(self, api: Api):
        """EBUS State Sensor."""
        super().__init__(api, "state")

    @property
    def name(self) -> str:
        """Return the name."""
        return "EBUS Status"

    @property
    def state(self):
        """Return the state."""
        return self._api.monitor.state

    @property
    def device_state_attributes(self):
        """Device State Attributes."""
        return self._api.monitor.info

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(self._api.subscribe(self))
