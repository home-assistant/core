"""Lightlink channels module for Zigbee Home Automation."""
import asyncio

import zigpy.exceptions
import zigpy.zcl.clusters.lightlink as lightlink

from .. import registries
from .base import ChannelStatus, ZigbeeChannel


@registries.CHANNEL_ONLY_CLUSTERS.register(lightlink.LightLink.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(lightlink.LightLink.cluster_id)
class LightLink(ZigbeeChannel):
    """Lightlink channel."""

    async def async_configure(self) -> None:
        """Add Coordinator to LightLink group ."""

        if self._ch_pool.skip_configuration:
            self._status = ChannelStatus.CONFIGURED
            return

        application = self._ch_pool.endpoint.device.application
        try:
            coordinator = application.get_device(application.ieee)
        except KeyError:
            self.warning("Aborting - unable to locate required coordinator device.")
            return

        try:
            _, _, groups = await self.cluster.get_group_identifiers(0)
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as exc:
            self.warning("Couldn't get list of groups: %s", str(exc))
            return

        if groups:
            for group in groups:
                self.debug("Adding coordinator to 0x%04x group id", group.group_id)
                await coordinator.add_to_group(group.group_id)
        else:
            await coordinator.add_to_group(0x0000, name="Default Lightlink Group")
