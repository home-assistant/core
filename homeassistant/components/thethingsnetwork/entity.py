"""Support for The Things Network entities."""

import logging

from ttn_client import TTNBaseValue

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TTNCoordinator

_LOGGER = logging.getLogger(__name__)


class TTNEntity(CoordinatorEntity[TTNCoordinator]):
    """Representation of a The Things Network Data Storage sensor."""

    _attr_has_entity_name = True
    _ttn_value: TTNBaseValue

    def __init__(
        self,
        coordinator: TTNCoordinator,
        app_id: str,
        ttn_value: TTNBaseValue,
    ) -> None:
        """Initialize a The Things Network Data Storage sensor."""

        # Pass coordinator to CoordinatorEntity
        super().__init__(coordinator)

        self._ttn_value = ttn_value

        self._attr_unique_id = f"{self.device_id}_{self.field_id}"
        self._attr_name = self.field_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{app_id}_{self.device_id}")},
            name=self.device_id,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        my_entity_update = self.coordinator.data.get(self.device_id, {}).get(
            self.field_id
        )
        if (
            my_entity_update
            and my_entity_update.received_at > self._ttn_value.received_at
        ):
            _LOGGER.debug(
                "Received update for %s: %s", self.unique_id, my_entity_update
            )
            # Check that the type of an entity has not changed since the creation
            assert isinstance(my_entity_update, type(self._ttn_value))
            self._ttn_value = my_entity_update
            self.async_write_ha_state()

    @property
    def device_id(self) -> str:
        """Return device_id."""
        return str(self._ttn_value.device_id)

    @property
    def field_id(self) -> str:
        """Return field_id."""
        return str(self._ttn_value.field_id)
