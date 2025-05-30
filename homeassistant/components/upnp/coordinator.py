"""UPnP/IGD coordinator."""

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta

from async_upnp_client.exceptions import UpnpCommunicationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER
from .device import Device

type UpnpConfigEntry = ConfigEntry[UpnpDataUpdateCoordinator]


class UpnpDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, str | datetime | int | float | None]]
):
    """Define an object to update data from UPNP device."""

    config_entry: UpnpConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UpnpConfigEntry,
        device: Device,
        device_entry: DeviceEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.device = device
        self.device_entry = device_entry
        self._features_by_entity_id: defaultdict[str, set[str]] = defaultdict(set)

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=device.name,
            update_interval=update_interval,
        )

    def register_entity(self, key: str, entity_id: str) -> Callable[[], None]:
        """Register an entity."""
        self._features_by_entity_id[key].add(entity_id)

        def unregister_entity() -> None:
            """Unregister entity."""
            self._features_by_entity_id[key].remove(entity_id)

            if not self._features_by_entity_id[key]:
                del self._features_by_entity_id[key]

        return unregister_entity

    @property
    def _entity_description_keys(self) -> list[str] | None:
        """Return a list of entity description keys for which data is required."""
        if not self._features_by_entity_id:
            # Must be the first update, no entities attached/enabled yet.
            return None

        return list(self._features_by_entity_id)

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
