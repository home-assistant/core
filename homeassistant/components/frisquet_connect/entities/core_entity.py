from abc import abstractmethod
import logging
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.core import callback

from frisquet_connect.const import DEVICE_MANUFACTURER, DOMAIN
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.utils import log_methods


_LOGGER = logging.getLogger(__name__)


# https://developers.home-assistant.io/docs/integration_fetching_data?_highlight=scan_interval#separate-polling-for-each-individual-entity
# https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling?_highlight=_attr_should_poll#example-implementation
@log_methods
class CoreEntity(CoordinatorEntity[FrisquetConnectCoordinator]):
    """Base class for all entities."""

    def __init__(self, coordinator: FrisquetConnectCoordinator) -> None:
        super().__init__(coordinator)
        _LOGGER.debug(f"Creating CoreEntity '{self.__class__.__name__}'")

        self._attr_has_entity_name = True
        self._attr_should_poll = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.site_id)},
            name=self.coordinator.data.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=str(self.coordinator.data.product),
            serial_number=self.coordinator.data.serial_number,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.update()
        super()._handle_coordinator_update()

    async def async_update(self) -> None:
        self.update()
        await super().async_update()

    @abstractmethod
    def update(self):
        _LOGGER.debug(f"{self.__class__.__name__}.CoreEntity.update() called")
