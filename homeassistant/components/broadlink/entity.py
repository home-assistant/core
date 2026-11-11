"""Broadlink entities."""

from typing import Any, override

from broadlink_async.magic import ImportedDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, magic_family_identifier
from .coordinator import FamilyCoordinator


class BroadlinkEntity(Entity):
    """Representation of a Broadlink entity."""

    _attr_should_poll = False

    def __init__(self, device):
        """Initialize the entity."""
        self._device = device
        self._coordinator = device.update_manager.coordinator

    @override
    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self._recv_data))
        if self._coordinator.data:
            self._update_state(self._coordinator.data)

    async def async_update(self) -> None:
        """Update the state of the entity."""
        await self._coordinator.async_request_refresh()

    def _recv_data(self):
        """Receive data from the update coordinator.

        This event listener should be called by the coordinator whenever
        there is an update available.

        It works as a template for the _update_state() method, which should
        be overridden by child classes in order to update the state of the
        entities, when applicable.
        """
        if self._coordinator.last_update_success:
            self._update_state(self._coordinator.data)
        self.async_write_ha_state()

    def _update_state(self, data):
        """Update the state of the entity.

        This method should be overridden by child classes in order to
        internalize state and attributes received from the coordinator.
        """

    @property
    @override
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self._device.available

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device = self._device

        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac_address)},
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer=device.api.manufacturer,
            model=device.api.model,
            name=device.name,
            sw_version=str(device.fw_version)
            if device.fw_version is not None
            else None,
        )


class BroadLinkMagicEntity(CoordinatorEntity[FamilyCoordinator]):
    """Base class for entities of an imported Magic Home family."""

    _attr_has_entity_name = True

    def _family_device_id(self) -> str:
        """Return the registry id of the imported family device."""
        return dr.async_get_device_id_by_identifier(
            self.coordinator.hass,
            (DOMAIN, magic_family_identifier(self.coordinator.family.family_id)),
            config_entry_id=self.coordinator.config_entry.entry_id,
        )

    def _confirmed_state(
        self, device: ImportedDevice, pending: dict[str, int]
    ) -> dict[str, Any]:
        """Return reported values that do not contradict pending commands.

        A periodic report sent before a command took effect still carries the
        old value, so a pending key is only applied once a report confirms it.
        """
        state: dict[str, Any] = {}
        for key, value in self.coordinator.device_states.get(
            device.stable_id, {}
        ).items():
            if key not in pending:
                state[key] = value
            elif int(value) == pending[key]:
                pending.pop(key)
                state[key] = value
        return state

    @property
    @override
    def available(self) -> bool:
        """Return whether at least one family gateway is online."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.gateway_set.online_gateways
        )
