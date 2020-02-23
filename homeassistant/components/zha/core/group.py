"""Group for Zigbee Home Automation."""
import asyncio
import logging

from homeassistant.core import callback

from .helpers import LogMixin

_LOGGER = logging.getLogger(__name__)


class ZHAGroup(LogMixin):
    """ZHA Zigbee group object."""

    def __init__(self, hass, zha_gateway, zigpy_group):
        """Initialize the group."""
        self.hass = hass
        self._zigpy_group = zigpy_group
        self._zha_gateway = zha_gateway

    @property
    def name(self):
        """Return group name."""
        return self._zigpy_group.name

    @property
    def group_id(self):
        """Return group name."""
        return self._zigpy_group.group_id

    @property
    def endpoint(self):
        """Return the endpoint for this group."""
        return self._zigpy_group.endpoint

    @property
    def members(self):
        """Return the ZHA devices that are members of this group."""
        return [
            self._zha_gateway.devices.get(member_ieee[0])
            for member_ieee in self._zigpy_group.members.keys()
            if member_ieee[0] in self._zha_gateway.devices
        ]

    async def async_add_members(self, member_ieee_addresses):
        """Add members to this group."""
        if len(member_ieee_addresses) > 1:
            tasks = []
            for ieee in member_ieee_addresses:
                tasks.append(
                    self._zha_gateway.devices[ieee].async_add_to_group(self.group_id)
                )
            await asyncio.gather(*tasks)
        else:
            await self._zha_gateway.devices[
                member_ieee_addresses[0]
            ].async_add_to_group(self.group_id)

    async def async_remove_members(self, member_ieee_addresses):
        """Remove members from this group."""
        if len(member_ieee_addresses) > 1:
            tasks = []
            for ieee in member_ieee_addresses:
                tasks.append(
                    self._zha_gateway.devices[ieee].async_remove_from_group(
                        self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            await self._zha_gateway.devices[
                member_ieee_addresses[0]
            ].async_remove_from_group(self.group_id)

    @callback
    def async_get_info(self):
        """Get ZHA group info."""
        group_info = {}
        group_info["group_id"] = self.group_id
        group_info["name"] = self.name
        group_info["members"] = [
            zha_device.async_get_info() for zha_device in self.members
        ]
        return group_info

    def log(self, level, msg, *args):
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.name, self.group_id) + args
        _LOGGER.log(level, msg, *args)
