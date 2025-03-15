"""Support for dobiss switches."""
import logging

from dobissapi import ICON_FROM_DOBISS, DobissSwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobissswitch."""

    _LOGGER.debug(f"Setting up switch component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    d_entities = dobiss.get_devices_by_type(DobissSwitch)
    entities = []
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        if not d.buddy:
            entities.append(HADobissSwitch(d))
    if entities:
        async_add_entities(entities)


class HADobissSwitch(SwitchEntity):
    """Dobiss switch device."""

    should_poll = False

    def __init__(self, dobissswitch: DobissSwitch):
        """Init dobiss Switch device."""
        super().__init__()
        self._dobissswitch = dobissswitch

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, f"address_{self._dobissswitch.address}")},
            "name": f"Dobiss Device {self._dobissswitch.address}",
            "manufacturer": "dobiss",
        }

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        return self._dobissswitch.attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON_FROM_DOBISS[self._dobissswitch.icons_id]

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobissswitch.register_callback(self.async_write_ha_state)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.signal_handler)
        )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobissswitch.remove_callback(self.async_write_ha_state)

    async def signal_handler(self, data):
        """Handle domain-specific signal by calling appropriate method."""
        entity_ids = data[ATTR_ENTITY_ID]

        if entity_ids == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            await getattr(self, data["method"])(**params)

    async def turn_on_service(self, brightness=None, delayon=None, delayoff=None):
        await self._dobissswitch.turn_on(
            brightness=brightness, delayon=delayon, delayoff=delayoff
        )

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._dobissswitch.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on or control the switch."""
        await self._dobissswitch.turn_on(**kwargs)

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self._dobissswitch.turn_off()

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._dobissswitch.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._dobissswitch.object_id
