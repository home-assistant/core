"""
Device tracker on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/device_tracker.zha/
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.components.zha.const import DATA_ZHA
import homeassistant.components.zha.entities as zha_entities
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


async def async_setup_entry(hass, entry, async_see):
    """Set up Zigbee Home Automation sensors."""
    device_trackers = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if device_trackers is not None:
        for device_tracker in device_trackers.values():
            tracker = ZhaDeviceTracker(async_see, **device_tracker)

            await tracker.async_added_to_hass()
            await tracker.async_update()

        del hass.data[DATA_ZHA][DOMAIN]

    return True


class ZhaDeviceTracker(zha_entities.ZhaEntity):
    """Zha device tracker."""

    _domain = DOMAIN

    def __init__(self, async_see, **kwargs):
        """Initialize the Tracker."""
        self._async_see = async_see
        super().__init__(**kwargs)

    async def async_update(self) -> None:
        """Update the device info."""
        dev_id = self.entity_id.split(".", 1)[1]
        name = None
        if 'friendly_name' in self._device_state_attributes:
            name = self._device_state_attributes['friendly_name']

        _LOGGER.debug('Updating %s', dev_id)

        await self._async_see(
            dev_id=dev_id,
            host_name=name,
            consider_home=timedelta(seconds=60)
        )

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""
        asyncio.ensure_future(self.async_update())

    @callback
    def attribute_updated(self, attribute, value):
        """Handle tracking."""
        asyncio.ensure_future(self.async_update())
