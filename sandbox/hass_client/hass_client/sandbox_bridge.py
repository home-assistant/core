"""Channel-backed :class:`SandboxBridge` for the sandbox runtime."""

import logging
from typing import Any

from homeassistant.helpers import json as json_helper
from homeassistant.util.json import SerializationError

from ._proto import sandbox_pb2 as pb
from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .messages import MSG_STORE_LOAD, MSG_STORE_REMOVE, MSG_STORE_SAVE, decode_json_dict

_LOGGER = logging.getLogger(__name__)


class ChannelSandboxBridge:
    """Route ``Store`` IO to main over a :class:`Channel`."""

    def __init__(self, channel: Channel) -> None:
        """Bind the bridge to the runtime's control channel."""
        self._channel = channel

    async def async_store_load(self, key: str) -> Any:
        """Fetch the wrapped envelope for ``key`` from main."""
        try:
            result = await self._channel.call(MSG_STORE_LOAD, pb.StoreLoad(key=key))
        except ChannelClosedError:
            _LOGGER.warning("sandbox store[%s]: channel closed mid-load", key)
            return None
        except ChannelRemoteError as err:
            _LOGGER.warning("sandbox store[%s] load failed: %s", key, err)
            return None
        if not result.HasField("data"):
            return None
        return decode_json_dict(result.data)

    async def async_store_save(self, key: str, data: Any) -> None:
        """Push the wrapped payload to main instead of writing to disk."""
        if "data_func" in data:
            data["data"] = data.pop("data_func")()
        try:
            _mode, json_data = json_helper.prepare_save_json(data, encoder=None)
        except SerializationError:
            _LOGGER.exception("sandbox store[%s]: payload not serialisable", key)
            return
        json_bytes = (
            json_data if isinstance(json_data, bytes) else json_data.encode("utf-8")
        )
        try:
            await self._channel.call(
                MSG_STORE_SAVE, pb.StoreSave(key=key, data=json_bytes)
            )
        except ChannelClosedError:
            _LOGGER.warning("sandbox store[%s]: channel closed mid-save", key)
        except ChannelRemoteError as err:
            _LOGGER.error("sandbox store[%s] save failed: %s", key, err)

    async def async_store_remove(self, key: str) -> None:
        """Unlink ``key`` on main, not on local disk."""
        try:
            await self._channel.call(MSG_STORE_REMOVE, pb.StoreRemove(key=key))
        except ChannelClosedError:
            _LOGGER.warning("sandbox store[%s]: channel closed mid-remove", key)
        except ChannelRemoteError as err:
            _LOGGER.warning("sandbox store[%s] remove failed: %s", key, err)


__all__ = ["ChannelSandboxBridge"]
