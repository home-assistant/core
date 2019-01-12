"""
Switches on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/switch.zha/
"""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components.zha import helpers
from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, REPORT_CONFIG_IMMEDIATE, ZHA_DISCOVERY_NEW)
from homeassistant.components.zha.entities import ZhaEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation switches."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation switch from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    switches = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if switches is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    switches.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA switches."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(Switch(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class Switch(ZhaEntity, SwitchDevice):
    """ZHA switch."""

    _domain = DOMAIN
    value_attribute = 0

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        cluster = self._endpoint.on_off
        attr_name = cluster.attributes.get(attribute, [attribute])[0]
        _LOGGER.debug("%s: Attribute '%s' on cluster '%s' updated to %s",
                      self.entity_id, attr_name, cluster.ep_attribute, value)
        if attribute == self.value_attribute:
            self._state = value
            self.async_schedule_update_ha_state()

    @property
    def zcl_reporting_config(self) -> dict:
        """Retrun a dict of attribute reporting configuration."""
        return {
            self.cluster: {'on_off': REPORT_CONFIG_IMMEDIATE}
        }

    @property
    def cluster(self):
        """Entity's cluster."""
        return self._endpoint.on_off

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return bool(self._state)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        from zigpy.exceptions import DeliveryError
        try:
            res = await self._endpoint.on_off.on()
            _LOGGER.debug("%s: turned 'on': %s", self.entity_id, res[1])
        except DeliveryError as ex:
            _LOGGER.error("%s: Unable to turn the switch on: %s",
                          self.entity_id, ex)
            return

        self._state = 1
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        from zigpy.exceptions import DeliveryError
        try:
            res = await self._endpoint.on_off.off()
            _LOGGER.debug("%s: turned 'off': %s", self.entity_id, res[1])
        except DeliveryError as ex:
            _LOGGER.error("%s: Unable to turn the switch off: %s",
                          self.entity_id, ex)
            return

        self._state = 0
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        result = await helpers.safe_read(self.cluster,
                                         ['on_off'],
                                         allow_cache=False,
                                         only_cache=(not self._initialized))
        self._state = result.get('on_off', self._state)
