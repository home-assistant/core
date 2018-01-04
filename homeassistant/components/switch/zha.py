"""
Switches on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/switch.zha/
"""
import asyncio
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components import zha

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation switches."""
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    async_add_devices([Switch(**discovery_info)], update_before_add=True)


class Switch(zha.Entity, SwitchDevice):
    """ZHA switch."""

    _domain = DOMAIN

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state == 'unknown':
            return False
        return bool(self._state)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        yield from self._endpoint.on_off.on()
        self._state = 1

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        yield from self._endpoint.on_off.off()
        self._state = 0

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s async_update", self.entity_id)

        @asyncio.coroutine
        def safe_read(cluster, attributes):
            """Swallow all exceptions from network read.

            If we throw during initialization, setup fails. Rather have an
            entity that exists, but is in a maybe wrong state, than no entity.
            """
            try:
                result, _ = yield from cluster.read_attributes(
                    attributes,
                    allow_cache=False,
                )
                return result
            except Exception:  # pylint: disable=broad-except
                return {}

        result = yield from safe_read(self._endpoint.on_off, ['on_off'])
        self._state = result.get('on_off', self._state)
