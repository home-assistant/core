"""Platform for Husqvarna Automower base entity."""

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

from . import AutomowerDataUpdateCoordinator
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


class AutomowerBaseEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        mower_id: int,
        snapshot: Snapshot,
        container: Container,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator)
        _LOGGER.debug("mower_id %s", mower_id)
        self.mower_id = mower_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            manufacturer="Husqvarna",
            name=self.mower_attributes.name,
            serial_number=self.mower_attributes.status,
        )
        self.snapshot = snapshot
        self.container = container

    @property
    def mower_attributes(self) -> NodeData:
        """Get the mower attributes of the current mower."""
        return self.coordinator.data[self.mower_id]

    @property
    def container_attributes(self) -> Container | None:
        """Get the mower attributes of the current mower."""
        for node_id in self.coordinator.data:
            for snapshot in self.coordinator.data[node_id].snapshots:
                for container in snapshot.docker_snapshot_raw.containers:
                    return container
        return None

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available
