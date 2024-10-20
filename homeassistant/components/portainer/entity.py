"""Platform for Portainer base entity."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any

from aiotainer.exceptions import ApiException
from aiotainer.model import Container, NodeData, Snapshot

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PortainerDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


EXECUTION_TIME_DELAY = 5


def handle_sending_exception(
    poll_after_sending: bool = False,
) -> Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Coroutine[Any, Any, None]]
]:
    """Handle exceptions while sending a command and optionally refresh coordinator."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                await func(self, *args, **kwargs)
            except ApiException as exception:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_send_failed",
                    translation_placeholders={"exception": str(exception)},
                ) from exception
            else:
                if poll_after_sending:
                    # As there are no updates from the websocket for this attribute,
                    # we need to wait until the command is executed and then poll the API.
                    await asyncio.sleep(EXECUTION_TIME_DELAY)
                    await self.coordinator.async_request_refresh()

        return wrapper

    return decorator


class SnapshotBaseEntity(CoordinatorEntity[PortainerDataUpdateCoordinator]):
    """Defining the Portainer base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        snapshot: Snapshot,
    ) -> None:
        """Initialize PortainerEntity."""
        super().__init__(coordinator)
        self.node_id = node_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node_id)},
            name=self.node_attributes.name,
        )
        self.snapshot = snapshot

    @property
    def node_attributes(self) -> NodeData:
        """Get the node attributes of the current node."""
        return self.coordinator.data[self.node_id]

    @property
    def snapshot_attributes(self) -> Container | None:
        """Get the node attributes of the current node."""
        for node_id in self.coordinator.data:
            for snapshot in self.coordinator.data[node_id].snapshots:
                return snapshot
        return None

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available


class ContainerBaseEntity(SnapshotBaseEntity):
    """Defining the Portainer base Entity."""

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        snapshot: Snapshot,
        container: Container,
    ) -> None:
        """Initialize PortainerEntity."""
        super().__init__(coordinator, node_id, snapshot)

    @property
    def container_attributes(self) -> Container | None:
        """Get the node attributes of the current node."""
        for node_id in self.coordinator.data:
            for snapshot in self.coordinator.data[node_id].snapshots:
                for container in snapshot.docker_snapshot_raw.containers:
                    return container
        return None
