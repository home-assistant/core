"""
Fans on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/fan.zha/
"""
import logging

from homeassistant.components.fan import (
    DOMAIN, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF, SUPPORT_SET_SPEED,
    FanEntity)
from homeassistant.components.zha import helpers
from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, REPORT_CONFIG_OP, ZHA_DISCOVERY_NEW)
from homeassistant.components.zha.entities import ZhaEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['zha']

_LOGGER = logging.getLogger(__name__)

# Additional speeds in zigbee's ZCL
# Spec is unclear as to what this value means. On King Of Fans HBUniversal
# receiver, this means Very High.
SPEED_ON = 'on'
# The fan speed is self-regulated
SPEED_AUTO = 'auto'
# When the heated/cooled space is occupied, the fan is always on
SPEED_SMART = 'smart'

SPEED_LIST = [
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SPEED_ON,
    SPEED_AUTO,
    SPEED_SMART
]

VALUE_TO_SPEED = {i: speed for i, speed in enumerate(SPEED_LIST)}
SPEED_TO_VALUE = {speed: i for i, speed in enumerate(SPEED_LIST)}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation fans."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation fan from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    fans = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if fans is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    fans.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA fans."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(ZhaFan(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class ZhaFan(ZhaEntity, FanEntity):
    """Representation of a ZHA fan."""

    _domain = DOMAIN
    value_attribute = 0  # fan_mode

    @property
    def zcl_reporting_config(self) -> dict:
        """Return a dict of attribute reporting configuration."""
        return {
            self.cluster: {self.value_attribute: REPORT_CONFIG_OP}
        }

    @property
    def cluster(self):
        """Fan ZCL Cluster."""
        return self._endpoint.fan

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state is None:
            return False
        return self._state != SPEED_OFF

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the entity on."""
        if speed is None:
            speed = SPEED_MEDIUM

        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self.async_set_speed(SPEED_OFF)

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        from zigpy.exceptions import DeliveryError
        try:
            await self._endpoint.fan.write_attributes(
                {'fan_mode': SPEED_TO_VALUE[speed]}
            )
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set speed: %s", self.entity_id, ex)
            return

        self._state = speed
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        result = await helpers.safe_read(self.cluster, ['fan_mode'],
                                         allow_cache=False,
                                         only_cache=(not self._initialized))
        new_value = result.get('fan_mode', None)
        self._state = VALUE_TO_SPEED.get(new_value, None)

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        attr_name = self.cluster.attributes.get(attribute, [attribute])[0]
        _LOGGER.debug("%s: Attribute report '%s'[%s] = %s",
                      self.entity_id, self.cluster.name, attr_name, value)
        if attribute == self.value_attribute:
            self._state = VALUE_TO_SPEED.get(value, self._state)
            self.async_schedule_update_ha_state()
