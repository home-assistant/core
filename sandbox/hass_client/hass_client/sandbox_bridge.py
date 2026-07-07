"""Channel-backed :class:`SandboxBridge` for the sandbox runtime.

Implements ``homeassistant.helpers.sandbox_context.SandboxBridge`` over the
control channel: the three ``Store`` IO methods delegate to main via the
``MSG_STORE_LOAD`` / ``MSG_STORE_SAVE`` / ``MSG_STORE_REMOVE`` RPCs. Main
namespaces every key as ``<config>/.storage/sandbox/<group>/<key>`` so
two sandbox processes — or main itself — can't read each other's data.

The bodies are lifted from the pre-contextvar store subclass that
this primitive replaced: same load semantics, same orjson preserialise on
save, same channel error handling. The difference is *how* it's wired —
``Store`` reads ``current_sandbox`` at call time instead of being rebound
at module scope.
"""

import logging
from typing import Any

from homeassistant.helpers import json as json_helper
from homeassistant.util.json import SerializationError

from ._proto import sandbox_pb2 as pb
from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .messages import decode_json_dict
from .protocol import MSG_STORE_LOAD, MSG_STORE_REMOVE, MSG_STORE_SAVE

_LOGGER = logging.getLogger(__name__)


class ChannelSandboxBridge:
    """Route ``Store`` IO to main over a :class:`Channel`.

    One bridge per sandbox runtime; the runtime sets it on
    ``current_sandbox`` once ``run()`` opens the channel, and every
    ``Store`` instance the sandbox builds resolves it at IO time.
    """

    def __init__(self, channel: Channel) -> None:
        """Bind the bridge to the runtime's control channel."""
        self._channel = channel

    async def async_store_load(self, key: str) -> Any:
        """Fetch the wrapped envelope for ``key`` from main.

        Returns the wrapped dict (``{"version", "minor_version", "key",
        "data"}``) so ``Store``'s migration loop runs against it unchanged,
        or ``None`` when main has no data / the channel is unavailable.
        """
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
        """Push the wrapped payload to main instead of writing to disk.

        ``Store`` callers may hand us HA-specific types (``Fragment`` from
        ``State.json_fragment``, ``set``/``tuple``, ``datetime``, ``Path``,
        ``as_dict``-shaped objects). The wire field carries JSON bytes, so
        the payload is run through orjson's HA-aware encoder — the same trip
        ``Store.async_save`` would take on its way to disk — and the bytes
        ship as-is, no re-parse.
        """
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
