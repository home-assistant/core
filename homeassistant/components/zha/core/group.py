"""Group for Zigbee Home Automation."""
import asyncio
import logging
from typing import Any, Dict, List

from zigpy.types.named import EUI64

from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import HomeAssistantType

from .helpers import LogMixin
from .typing import ZhaDeviceType, ZhaGatewayType, ZigpyEndpointType, ZigpyGroupType

_LOGGER = logging.getLogger(__name__)


class ZHAGroup(LogMixin):
    """ZHA Zigbee group object."""

    def __init__(
        self,
        hass: HomeAssistantType,
        zha_gateway: ZhaGatewayType,
        zigpy_group: ZigpyGroupType,
    ):
        """Initialize the group."""
        self.hass: HomeAssistantType = hass
        self._zigpy_group: ZigpyGroupType = zigpy_group
        self._zha_gateway: ZhaGatewayType = zha_gateway

    @property
    def name(self) -> str:
        """Return group name."""
        return self._zigpy_group.name

    @property
    def group_id(self) -> int:
        """Return group name."""
        return self._zigpy_group.group_id

    @property
    def endpoint(self) -> ZigpyEndpointType:
        """Return the endpoint for this group."""
        return self._zigpy_group.endpoint

    @property
    def members(self) -> List[ZhaDeviceType]:
        """Return the ZHA devices that are members of this group."""
        return [
            self._zha_gateway.devices.get(member_ieee[0])
            for member_ieee in self._zigpy_group.members.keys()
            if member_ieee[0] in self._zha_gateway.devices
        ]

    async def async_add_members(self, member_ieee_addresses: List[EUI64]) -> None:
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

    async def async_remove_members(self, member_ieee_addresses: List[EUI64]) -> None:
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

    @property
    def member_entity_ids(self) -> List[str]:
        """Return the ZHA entity ids for all entities for the members of this group."""
        all_entity_ids: List[str] = []
        for device in self.members:
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry, device.device_id
            )
            for entity in entities:
                all_entity_ids.append(entity.entity_id)
        return all_entity_ids

    def get_domain_entity_ids(self, domain) -> List[str]:
        """Return entity ids from the entity domain for this group."""
        domain_entity_ids: List[str] = []
        for device in self.members:
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry, device.device_id
            )
            domain_entity_ids.extend(
                [entity.entity_id for entity in entities if entity.domain == domain]
            )
        return domain_entity_ids

    @callback
    def async_get_info(self) -> Dict[str, Any]:
        """Get ZHA group info."""
        group_info: Dict[str, Any] = {}
        group_info["group_id"] = self.group_id
        group_info["name"] = self.name
        group_info["members"] = [
            zha_device.async_get_info() for zha_device in self.members
        ]
        return group_info

    def log(self, level: int, msg: str, *args):
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.name, self.group_id) + args
        _LOGGER.log(level, msg, *args)
