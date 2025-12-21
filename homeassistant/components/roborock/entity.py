"""Support for Roborock device base class."""

from typing import Any

from roborock.data import Status
from roborock.devices.traits.v1.command import CommandTrait
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
    RoborockDataUpdateCoordinatorB01,
)


class RoborockEntity(Entity):
    """Representation of a base Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Roborock Device."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info


class RoborockEntityV1(RoborockEntity):
    """Representation of a base Roborock V1 Entity."""

    def __init__(
        self, unique_id: str, device_info: DeviceInfo, api: CommandTrait
    ) -> None:
        """Initialize the Roborock Device."""
        super().__init__(unique_id, device_info)
        self._api = api

    async def send(
        self,
        command: RoborockCommand | str,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Send a Roborock command with params to a given api."""
        try:
            response: dict = await self._api.send(command, params=params)
        except RoborockException as err:
            if isinstance(command, RoborockCommand):
                command_name = command.name
            else:
                command_name = command
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": command_name,
                },
            ) from err
        return response


class RoborockCoordinatedEntityV1(
    RoborockEntityV1, CoordinatorEntity[RoborockDataUpdateCoordinator]
):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        is_dock_entity: bool = False,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntityV1.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info
            if not is_dock_entity
            else coordinator.dock_device_info,
            api=coordinator.properties_api.command,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id

    @property
    def _device_status(self) -> Status:
        """Return the status of the device."""
        data = self.coordinator.data
        return data.status

    async def send(
        self,
        command: RoborockCommand | str,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Overloads normal send command but refreshes coordinator."""
        res = await super().send(command, params)
        await self.coordinator.async_refresh()
        return res


class RoborockCoordinatedEntityA01(
    RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinatorA01]
):
    """Representation of a base a coordinated Roborock Entity."""

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinatorA01,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id


class RoborockCoordinatedEntityB01(
    RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinatorB01]
):
    """Representation of coordinated Roborock Entity."""

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinatorB01,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id
