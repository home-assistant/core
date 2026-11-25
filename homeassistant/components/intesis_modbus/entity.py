"""Base entity for Intesis Modbus gateways and the air conditioner behind them."""

from collections.abc import Awaitable, Callable
from typing import override

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntesisCoordinator, IntesisUnitCoordinator


class IntesisEntity(CoordinatorEntity[IntesisCoordinator | IntesisUnitCoordinator]):
    """Defines a base Intesis entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntesisCoordinator | IntesisUnitCoordinator,
        key: str,
        report_name: str,
    ) -> None:
        """Place the entity on the device its coordinator follows.

        That is the gateway, or the air conditioner behind it. report_name is
        the gateway sub-system the entity's value is read from.
        """
        super().__init__(coordinator)
        self._report_name = report_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info

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
        await self.coordinator.async_request_refresh()
