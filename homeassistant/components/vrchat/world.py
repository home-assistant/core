"""VRChat worlds."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging
from threading import Timer

from .api import VRChatAPI
from .api_data_types import World
from .const import RETRY_DELAY_SECOND

_LOGGER = logging.getLogger(__name__)

VRCHAT_WORLD_DATA_CACHE_TTL = timedelta(days=1)
VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND = 3600


class VRChatWorldData:
    """VRChat world data."""

    registry: dict[str, VRChatWorldData] = {}

    @classmethod
    def get(cls, world_id: str, data: World | None = None):
        """Get world data object. Update data if provided."""
        registry = cls.registry
        world = registry.get(world_id)
        if world is None:
            world = cls(world_id, data)
            registry[world_id] = world
        elif data is not None:
            world.data = data
        return world

    def __init__(self, world_id: str, data: World | None = None):
        """Initialization."""

        self.task: asyncio.Task[World] | None = None

        self.subscribers: list[Callable[[World | None], None]] = []

        self.id = world_id
        self.data = data

    @property
    def data(self):
        """The data."""
        return self._data

    @data.setter
    def data(self, new_data: World | None):
        self._data = new_data
        self.last_updated = datetime.now(UTC)
        for callback in self.subscribers:
            callback(new_data)

    @property
    def should_invalidate(self):
        """Check if the data cache should be invalidated."""
        return datetime.now(UTC) - self.last_updated > VRCHAT_WORLD_DATA_CACHE_TTL

    async def get_data(self):
        """Get data. Fetch if not exist."""
        if self.data is None:
            await asyncio.sleep(1)
        if self.data is None or self.should_invalidate:
            if self.task is None:
                self.task = asyncio.create_task(self._get_data())
            await self.task
        return self.data

    async def _get_data(self):
        try:
            async with VRChatAPI() as api:
                data = await asyncio.wait_for(
                    api.get_world(self.id), RETRY_DELAY_SECOND
                )
                self.data = data
                self.task = None
                return data
        except TimeoutError:
            _LOGGER.exception("Fetch world data timed out. Retrying. ID: %s", self.id)
            return await self._get_data()
        except Exception:
            _LOGGER.exception(
                "Fetch world data failed. Retrying in %s seconds. ID: %s",
                RETRY_DELAY_SECOND,
                self.id,
            )
            await asyncio.sleep(RETRY_DELAY_SECOND)
            return await self._get_data()

    def subscribe(self, callback: Callable[[World | None], None]) -> Callable[[], None]:
        """Subscribe to data update."""
        self.subscribers.append(callback)

        def unsubscribe():
            self.unsubscribe(callback)

        return unsubscribe

    def unsubscribe(self, callback: Callable[[World | None], None]) -> None:
        """Unsubscribe from data update."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)


def _prune_unused_world_data():
    registry = VRChatWorldData.registry
    for world_id, world in registry.items():
        if world.should_invalidate and len(world.subscribers) <= 0:
            del registry[world_id]
    Timer(
        VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND, _prune_unused_world_data
    ).start()


Timer(VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND, _prune_unused_world_data).start()
