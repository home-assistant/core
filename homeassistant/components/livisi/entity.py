"""Code to handle a Livisi switches."""

from abc import abstractmethod
import asyncio
from typing import override

from livisi import LivisiDevice

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LIVISI_REACHABILITY_CHANGE
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator


class LivisiEntity(CoordinatorEntity[LivisiDataUpdateCoordinator]):
    """Represents a base livisi entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        *,
        use_room_as_device_name: bool = False,
    ) -> None:
        """Initialize the common properties of a Livisi device."""
        self.aio_livisi = coordinator.aiolivisi
        self.capabilities = device.capabilities
        self._device_id = device.id

        name = device.name

        room_name: str | None = device.room

        self._attr_available = not device.unreachable
        self._attr_unique_id = self._device_id
        self._reachability_generation = 0
        self._recovery_task: asyncio.Task[None] | None = None

        device_name = name

        # For livisi climate entities, the device should have the room name from
        # the livisi setup, as each livisi room gets exactly one VRCC device. The entity
        # name will always be some localized value of
        # "Climate", so the full element name
        # in homeassistent will be in the form of "Bedroom Climate"
        if use_room_as_device_name and room_name is not None:
            self._attr_name = name
            device_name = room_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=device.manufacturer,
            model=device.type,
            name=device_name,
            suggested_area=room_name,
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, config_entry.entry_id),
                config_entry_id=config_entry.entry_id,
            ),
        )
        super().__init__(coordinator)

    @property
    @override
    def available(self) -> bool:
        """Return whether the device and coordinator are available."""
        return self._attr_available and super().available

    @override
    async def async_added_to_hass(self) -> None:
        """Register callback for reachability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{self._device_id}",
                self.update_reachability,
            )
        )
        self.async_on_remove(self._cancel_recovery_task)

    @abstractmethod
    async def async_update_value(self) -> bool:
        """Update the entity value and return whether the read succeeded."""

    @callback
    def update_reachability(self, is_reachable: bool, generation: int) -> None:
        """Update the reachability of the device."""
        if generation < self._reachability_generation:
            return
        self._reachability_generation = generation
        if not is_reachable:
            self._cancel_recovery_task()
            self._attr_available = False
            self.async_write_ha_state()
            return

        if self._recovery_task is not None and not self._recovery_task.done():
            return
        self._recovery_task = self.hass.async_create_task(
            self._async_recover(generation)
        )

    async def _async_recover(self, generation: int) -> None:
        """Refresh state before marking the device reachable."""
        this_task = asyncio.current_task()
        try:
            update_success = await self.async_update_value()
            if generation != self._reachability_generation:
                return
            if update_success and self.coordinator.confirm_device_reachable(
                self._device_id, generation
            ):
                self._attr_available = True
            self.async_write_ha_state()
        finally:
            if self._recovery_task is this_task:
                self._recovery_task = None

    @callback
    def _cancel_recovery_task(self) -> None:
        """Cancel an in-flight recovery read."""
        if self._recovery_task is not None and not self._recovery_task.done():
            self._recovery_task.cancel()
        self._recovery_task = None
