"""Base entity for Intesis Modbus gateways."""

from collections.abc import Awaitable, Callable
from typing import override

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MODEL, DOMAIN
from .coordinator import IntesisCoordinator

MANUFACTURER = "Intesis (HMS Networks)"


class IntesisEntity(CoordinatorEntity[IntesisCoordinator]):
    """Defines a base Intesis entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: IntesisCoordinator, key: str, report_name: str
    ) -> None:
        """Place the entity on the gateway.

        report_name is the gateway sub-system the entity's value is read from.
        """
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._report_name = report_name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=entry.data[CONF_MODEL],
            name=entry.title,
            sw_version=coordinator.device.software_version,
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
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
