"""Group for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
import collections
import logging
from typing import Any

import zigpy.exceptions

from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import HomeAssistantType

from .helpers import LogMixin
from .typing import (
    ZhaDeviceType,
    ZhaGatewayType,
    ZhaGroupType,
    ZigpyEndpointType,
    ZigpyGroupType,
)

_LOGGER = logging.getLogger(__name__)

GroupMember = collections.namedtuple("GroupMember", "ieee endpoint_id")
GroupEntityReference = collections.namedtuple(
    "GroupEntityReference", "name original_name entity_id"
)


class ZHAGroupMember(LogMixin):
    """Composite object that represents a device endpoint in a Zigbee group."""

    def __init__(
        self, zha_group: ZhaGroupType, zha_device: ZhaDeviceType, endpoint_id: int
    ):
        """Initialize the group member."""
        self._zha_group: ZhaGroupType = zha_group
        self._zha_device: ZhaDeviceType = zha_device
        self._endpoint_id: int = endpoint_id

    @property
    def group(self) -> ZhaGroupType:
        """Return the group this member belongs to."""
        return self._zha_group

    @property
    def endpoint_id(self) -> int:
        """Return the endpoint id for this group member."""
        return self._endpoint_id

    @property
    def endpoint(self) -> ZigpyEndpointType:
        """Return the endpoint for this group member."""
        return self._zha_device.device.endpoints.get(self.endpoint_id)

    @property
    def device(self) -> ZhaDeviceType:
        """Return the zha device for this group member."""
        return self._zha_device

    @property
    def member_info(self) -> dict[str, Any]:
        """Get ZHA group info."""
        member_info: dict[str, Any] = {}
        member_info["endpoint_id"] = self.endpoint_id
        member_info["device"] = self.device.zha_device_info
        member_info["entities"] = self.associated_entities
        return member_info

    @property
    def associated_entities(self) -> list[GroupEntityReference]:
        """Return the list of entities that were derived from this endpoint."""
        ha_entity_registry = self.device.gateway.ha_entity_registry
        zha_device_registry = self.device.gateway.device_registry
        return [
            GroupEntityReference(
                ha_entity_registry.async_get(entity_ref.reference_id).name,
                ha_entity_registry.async_get(entity_ref.reference_id).original_name,
                entity_ref.reference_id,
            )._asdict()
            for entity_ref in zha_device_registry.get(self.device.ieee)
            if list(entity_ref.cluster_channels.values())[
                0
            ].cluster.endpoint.endpoint_id
            == self.endpoint_id
        ]

    async def async_remove_from_group(self) -> None:
        """Remove the device endpoint from the provided zigbee group."""
        try:
            await self._zha_device.device.endpoints[
                self._endpoint_id
            ].remove_from_group(self._zha_group.group_id)
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to remove endpoint: %s for device '%s' from group: 0x%04x ex: %s",
                self._endpoint_id,
                self._zha_device.ieee,
                self._zha_group.group_id,
                str(ex),
            )

    def log(self, level: int, msg: str, *args) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (f"0x{self._zha_group.group_id:04x}", self.endpoint_id) + args
        _LOGGER.log(level, msg, *args)


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
    def members(self) -> list[ZHAGroupMember]:
        """Return the ZHA devices that are members of this group."""
        return [
            ZHAGroupMember(
                self, self._zha_gateway.devices.get(member_ieee), endpoint_id
            )
            for (member_ieee, endpoint_id) in self._zigpy_group.members.keys()
            if member_ieee in self._zha_gateway.devices
        ]

    async def async_add_members(self, members: list[GroupMember]) -> None:
        """Add members to this group."""
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    self._zha_gateway.devices[member.ieee].async_add_endpoint_to_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            await self._zha_gateway.devices[
                members[0].ieee
            ].async_add_endpoint_to_group(members[0].endpoint_id, self.group_id)

    async def async_remove_members(self, members: list[GroupMember]) -> None:
        """Remove members from this group."""
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    self._zha_gateway.devices[
                        member.ieee
                    ].async_remove_endpoint_from_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            await self._zha_gateway.devices[
                members[0].ieee
            ].async_remove_endpoint_from_group(members[0].endpoint_id, self.group_id)

    @property
    def member_entity_ids(self) -> list[str]:
        """Return the ZHA entity ids for all entities for the members of this group."""
        all_entity_ids: list[str] = []
        for member in self.members:
            entity_references = member.associated_entities
            for entity_reference in entity_references:
                all_entity_ids.append(entity_reference["entity_id"])
        return all_entity_ids

    def get_domain_entity_ids(self, domain) -> list[str]:
        """Return entity ids from the entity domain for this group."""
        domain_entity_ids: list[str] = []
        for member in self.members:
            if member.device.is_coordinator:
                continue
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry,
                member.device.device_id,
                include_disabled_entities=True,
            )
            domain_entity_ids.extend(
                [entity.entity_id for entity in entities if entity.domain == domain]
            )
        return domain_entity_ids

    @property
    def group_info(self) -> dict[str, Any]:
        """Get ZHA group info."""
        group_info: dict[str, Any] = {}
        group_info["group_id"] = self.group_id
        group_info["name"] = self.name
        group_info["members"] = [member.member_info for member in self.members]
        return group_info

    def log(self, level: int, msg: str, *args):
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.name, self.group_id) + args
        _LOGGER.log(level, msg, *args)
