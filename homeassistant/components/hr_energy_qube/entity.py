"""Base entity for Qube Heat Pump."""

from typing import TYPE_CHECKING

from yarl import URL

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QubeCoordinator

if TYPE_CHECKING:
    from . import QubeConfigEntry


class QubeEntity(CoordinatorEntity[QubeCoordinator]):
    """Base entity for Qube Heat Pump."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="HR-energy",
            model="Qube",
            sw_version=coordinator.sw_version,
            configuration_url=URL.build(scheme="http", host=entry.data[CONF_HOST]),
        )
