"""Base entity for the air conditioner behind an Intesis Modbus gateway."""

from collections.abc import Awaitable, Callable
from typing import override

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntesisUnitCoordinator


class IntesisEntity(CoordinatorEntity[IntesisUnitCoordinator]):
    """Defines a base entity of the air conditioner."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: IntesisUnitCoordinator, key: str, report_name: str
    ) -> None:
        """Place the entity on the air conditioner behind the gateway.

        report_name is the gateway sub-system the entity's value is read from.
        """
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._report_name = report_name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_unit")},
            manufacturer=coordinator.device.brand.name,
            translation_key="air_conditioner",
            translation_placeholders={"gateway": entry.title},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, entry.entry_id),
                config_entry_id=entry.entry_id,
            ),
        )

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's value was read in the most recent poll."""
        return super().available and self._report_name in self.coordinator.data.updated

    async def _async_write(self, write: Callable[[], Awaitable[None]]) -> None:
        """Run one write against the gateway, then ask for a refresh."""
        try:
            await write()
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
            ) from err
        await self.coordinator.gateway.async_request_refresh()
