"""Support for The Things Network entities."""

from abc import ABC
import logging
from typing import TYPE_CHECKING, Optional

from ttn_client import TTNSensorValue

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .coordinator import TTNCoordinator

from .const import CONF_APP_ID

_LOGGER = logging.getLogger(__name__)


class TTNEntity(CoordinatorEntity["TTNCoordinator"], Entity, ABC):
    """Representation of a The Things Network Data Storage sensor."""

    @staticmethod
    def get_unique_id(device_id: str, field_id: str) -> str:
        """Get unique_id which is derived from device_id and field_id."""
        return f"{device_id}_{field_id}"

    def __init__(
        self,
        coordinator: "TTNCoordinator",
        ttn_value: TTNSensorValue,
    ) -> None:
        """Initialize a The Things Network Data Storage sensor."""

        self._entry = coordinator.config_entry
        self._ttn_value = ttn_value
        self._name = f"{self.device_name} {self.field_id}"

        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=self.unique_id)

    # ---------------
    # Coordinator method
    # ---------------

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        my_entity_update = self.coordinator.data.get(self.device_id, {}).get(
            self.field_id, None
        )
        if (
            my_entity_update
            and my_entity_update.received_at > self._ttn_value.received_at
        ):
            _LOGGER.debug(
                "Received update for %s: %s", self.unique_id, my_entity_update
            )
            self._ttn_value = my_entity_update
            self.async_write_ha_state()

    # ---------------
    # standard Entity propertiess
    # ---------------

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.get_unique_id(self.device_id, self.field_id)

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes.

        Implemented by platform classes.
        """
        assert self._entry
        return DeviceInfo(
            {
                "identifiers": {
                    # Serial numbers are unique identifiers within a specific domain
                    (self._entry.data[CONF_APP_ID], self.device_id)
                },
                "name": self.device_name,
                # TBD - add more info in the TTN upstream message such as signal strength, transmission time, etc
            }
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    # ---------------
    # TTN integration additional methods
    # ---------------
    @property
    def device_id(self) -> str:
        """Return device_id."""
        return str(self._ttn_value.device_id)

    @property
    def field_id(self) -> str:
        """Return field_id."""
        return str(self._ttn_value.field_id)

    @property
    def device_name(self) -> str:
        """Return device_name."""
        return self.device_id
