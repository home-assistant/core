"""
Switches on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/switch.zha/
"""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components import zha

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Zigbee Home Automation switches."""
    from zigpy.zcl.clusters.general import OnOff

    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    switch = Switch(**discovery_info)

    if discovery_info['new_join']:
        in_clusters = discovery_info['in_clusters']
        cluster = in_clusters[OnOff.cluster_id]
        await zha.configure_reporting(
            switch.entity_id, cluster, switch.value_attribute,
            min_report=0, max_report=600, reportable_change=1
        )

    async_add_entities([switch], update_before_add=True)


class Switch(zha.Entity, SwitchDevice):
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
    def should_poll(self) -> bool:
        """Let zha handle polling."""
        return False

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
        result = await zha.safe_read(self._endpoint.on_off,
                                     ['on_off'],
                                     allow_cache=False,
                                     only_cache=(not self._initialized))
        self._state = result.get('on_off', self._state)
