"""Support for Roborock device base class."""

from typing import Any

from roborock.api import AttributeCache, RoborockClient
from roborock.command_cache import CacheableAttribute
from roborock.containers import Status
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RoborockDataUpdateCoordinator


class RoborockEntity(Entity):
    """Representation of a base Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self, unique_id: str, device_info: DeviceInfo, api: RoborockClient
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._api = api

    @property
    def api(self) -> RoborockClient:
        """Returns the api."""
        return self._api

    def get_cache(self, attribute: CacheableAttribute) -> AttributeCache:
        """Get an item from the api cache."""
        return self._api.cache.get(attribute)

    async def send(
        self,
        command: RoborockCommand,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Send a command to a vacuum cleaner."""
        try:
            response = await self._api.send_command(command, params)
        except RoborockException as err:
            raise HomeAssistantError(
                f"Error while calling {command.name} with {params}"
            ) from err

        return response


class RoborockCoordinatedEntity(
    RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinator]
):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info,
            api=coordinator.api,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id

    @property
    def _device_status(self) -> Status:
        """Return the status of the device."""
        data = self.coordinator.data
        if data:
            status = data.status
            if status:
                return status
        return Status({})

    async def send(
        self,
        command: RoborockCommand,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Overloads normal send command but refreshes coordinator."""
        res = await super().send(command, params)
        await self.coordinator.async_refresh()
        return res
