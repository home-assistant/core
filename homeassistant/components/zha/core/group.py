"""Group for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

import zigpy.endpoint
import zigpy.exceptions
import zigpy.group
from zigpy.types.named import EUI64

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_device

from .helpers import LogMixin

if TYPE_CHECKING:
    from .device import ZHADevice
    from .gateway import ZHAGateway

_LOGGER = logging.getLogger(__name__)


class GroupMember(NamedTuple):
    """Describes a group member."""

    ieee: EUI64
    endpoint_id: int


class GroupEntityReference(NamedTuple):
    """Reference to a group entity."""

    name: str | None
    original_name: str | None
    entity_id: int


class ZHAGroupMember(LogMixin):
    """Composite object that represents a device endpoint in a Zigbee group."""

    def __init__(
        self, zha_group: ZHAGroup, zha_device: ZHADevice, endpoint_id: int
    ) -> None:
        """Initialize the group member."""
        self._zha_group = zha_group
        self._zha_device = zha_device
        self._endpoint_id = endpoint_id

    @property
    def group(self) -> ZHAGroup:
        """Return the group this member belongs to."""
        return self._zha_group

    @property
    def endpoint_id(self) -> int:
        """Return the endpoint id for this group member."""
        return self._endpoint_id

    @property
    def endpoint(self) -> zigpy.endpoint.Endpoint:
        """Return the endpoint for this group member."""
        return self._zha_device.device.endpoints.get(self.endpoint_id)

    @property
    def device(self) -> ZHADevice:
        """Return the ZHA device for this group member."""
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
    def associated_entities(self) -> list[dict[str, Any]]:
        """Return the list of entities that were derived from this endpoint."""
        entity_registry = er.async_get(self._zha_device.hass)
        zha_device_registry = self.device.gateway.device_registry

        entity_info = []

        for entity_ref in zha_device_registry.get(self.device.ieee):
            entity = entity_registry.async_get(entity_ref.reference_id)
            handler = list(entity_ref.cluster_handlers.values())[0]

            if (
                entity is None
                or handler.cluster.endpoint.endpoint_id != self.endpoint_id
            ):
                continue

            entity_info.append(
                GroupEntityReference(
                    name=entity.name,
                    original_name=entity.original_name,
                    entity_id=entity_ref.reference_id,
                )._asdict()
            )

        return entity_info

    async def async_remove_from_group(self) -> None:
        """Remove the device endpoint from the provided zigbee group."""
        try:
            await self._zha_device.device.endpoints[
                self._endpoint_id
            ].remove_from_group(self._zha_group.group_id)
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                (
                    "Failed to remove endpoint: %s for device '%s' from group: 0x%04x"
                    " ex: %s"
                ),
                self._endpoint_id,
                self._zha_device.ieee,
                self._zha_group.group_id,
                str(ex),
            )

    def log(self, level: int, msg: str, *args: Any, **kwargs) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (f"0x{self._zha_group.group_id:04x}", self.endpoint_id) + args
        _LOGGER.log(level, msg, *args, **kwargs)


class ZHAGroup(LogMixin):
    """ZHA Zigbee group object."""

    def __init__(
        self,
        hass: HomeAssistant,
        zha_gateway: ZHAGateway,
        zigpy_group: zigpy.group.Group,
    ) -> None:
        """Initialize the group."""
        self.hass = hass
        self._zha_gateway = zha_gateway
        self._zigpy_group = zigpy_group

    @property
    def name(self) -> str:
        """Return group name."""
        return self._zigpy_group.name

    @property
    def group_id(self) -> int:
        """Return group name."""
        return self._zigpy_group.group_id

    @property
    def endpoint(self) -> zigpy.endpoint.Endpoint:
        """Return the endpoint for this group."""
        return self._zigpy_group.endpoint

    @property
    def members(self) -> list[ZHAGroupMember]:
        """Return the ZHA devices that are members of this group."""
        return [
            ZHAGroupMember(self, self._zha_gateway.devices[member_ieee], endpoint_id)
            for (member_ieee, endpoint_id) in self._zigpy_group.members
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

    def get_domain_entity_ids(self, domain: str) -> list[str]:
        """Return entity ids from the entity domain for this group."""
        entity_registry = er.async_get(self.hass)
        domain_entity_ids: list[str] = []

        for member in self.members:
            if member.device.is_coordinator:
                continue
            entities = async_entries_for_device(
                entity_registry,
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

    def log(self, level: int, msg: str, *args: Any, **kwargs) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.name, self.group_id) + args
        _LOGGER.log(level, msg, *args, **kwargs)
