"""UPnP/IGD coordinator."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from async_upnp_client.exceptions import UpnpCommunicationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER
from .device import Device

if TYPE_CHECKING:
    from .entity import UpnpEntity


class UpnpDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, str | datetime | int | float | None]]
):
    """Define an object to update data from UPNP device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
        device_entry: DeviceEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.device = device
        self.device_entry = device_entry
        self._entities: list[UpnpEntity] = []

        super().__init__(
            hass,
            LOGGER,
            name=device.name,
            update_interval=update_interval,
        )

    def register_entity(self, entity) -> None:
        """Register an entity."""
        self._entities.append(entity)

    @property
    def _enabled_entities(self) -> list["UpnpEntity"]:
        """Return a list of enabled sensors."""
        return [entity for entity in self._entities if entity.enabled]

    @property
    def _entity_description_keys(self) -> list[str] | None:
        """Return a list of entity description keys for which data is required."""
        if not self._enabled_entities:
            # Must be the first update, no entities attached/enabled yet.
            return None

        return [entity.entity_description.key for entity in self._enabled_entities]

    async def _async_update_data(
        self,
    ) -> dict[str, str | datetime | int | float | None]:
        """Update data."""
        try:
            return await self.device.async_get_data(self._entity_description_keys)
        except UpnpCommunicationError as exception:
            LOGGER.debug(
                "Caught exception when updating device: %s, exception: %s",
                self.device,
                exception,
            )
            raise UpdateFailed(
                f"Unable to communicate with IGD at: {self.device.device_url}"
            ) from exception
