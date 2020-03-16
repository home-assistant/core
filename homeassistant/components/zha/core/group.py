"""Group for Zigbee Home Automation."""
import asyncio
from collections import Counter
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_entries_for_device

from .helpers import LogMixin
from .registries import GROUP_ENTITY_DOMAINS

_LOGGER = logging.getLogger(__name__)


class ZHAGroup(LogMixin):
    """ZHA Zigbee group object."""

    def __init__(self, hass, zha_gateway, zigpy_group):
        """Initialize the group."""
        self.hass = hass
        self._zigpy_group = zigpy_group
        self._zha_gateway = zha_gateway
        self._entity_domain = None
        self._determine_default_entity_domain()

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
    def entity_domain(self):
        """Return the domain that will be used for the entity representing this group."""
        return self._entity_domain

    @entity_domain.setter
    def entity_domain(self, domain):
        """Set the domain that will be used for the entity representing this group."""
        self._entity_domain = domain

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

    @property
    def member_entity_ids(self):
        """Return the ZHA entity ids for all entities for the members of this group."""
        all_entity_ids = []
        for device in self.members:
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry, device.device_id
            )
            for entity in entities:
                all_entity_ids.append(entity.entity_id)
        return all_entity_ids

    @property
    def domain_entity_ids(self):
        """Return entity ids from the entity domain for this group."""
        if self.entity_domain is None:
            return
        domain_entity_ids = []
        for device in self.members:
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry, device.device_id
            )
            domain_entity_ids.extend(
                [
                    entity.entity_id
                    for entity in entities
                    if entity.domain == self.entity_domain
                ]
            )
        return domain_entity_ids

    def _determine_default_entity_domain(self):
        """Determine the default entity domain for this group."""
        all_domain_occurrences = []
        for device in self.members:
            entities = async_entries_for_device(
                self._zha_gateway.ha_entity_registry, device.device_id
            )
            all_domain_occurrences.extend(
                [
                    entity.domain
                    for entity in entities
                    if entity.domain in GROUP_ENTITY_DOMAINS
                ]
            )
        counts = Counter(all_domain_occurrences)
        domain = counts.most_common(1)[0][0]
        self.warning("entity domain would be: %s", domain)

    @callback
    def async_get_info(self):
        """Get ZHA group info."""
        group_info = {}
        group_info["group_id"] = self.group_id
        group_info["entity_domain"] = self.entity_domain
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
