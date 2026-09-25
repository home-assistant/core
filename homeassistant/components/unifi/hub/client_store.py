"""Clients of the Network Integration API, kept across restarts.

The Integration API lists connected clients only and has no record of the
ones it has seen, unlike the classic API. Without this, a client that is
away when Home Assistant starts would have no tracker until it connects
again. Each entry set up with an API key keeps the clients it has seen,
with when they were last listed, and puts them back into the aiounifi
cache on start.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict

from aiounifi.network.v1.interfaces.clients import Clients
from aiounifi.network.v1.models.client import ClientData

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import CLIENT_RESTORE_MAX_AGE

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

STORAGE_VERSION = 1
SAVE_DELAY = 10


class StoredClient(TypedDict):
    """One client as stored."""

    raw: ClientData
    last_seen: str | None


def storage_key(config_entry: ConfigEntry) -> str:
    """Storage key of one config entry's clients."""
    return f"unifi_network_clients.{config_entry.entry_id}"


class UnifiNetworkClientStore:
    """Clients an API key entry has seen, persisted between restarts."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._store: Store[dict[str, StoredClient]] = Store(
            hass, STORAGE_VERSION, storage_key(config_entry)
        )
        self._clients: Clients | None = None
        self._stored: dict[str, StoredClient] = {}

    async def async_load(self) -> None:
        """Load the stored clients."""
        if (data := await self._store.async_load()) is not None:
            self._stored = data

    @callback
    def restore(self, clients: Clients, keep: set[str]) -> list[str]:
        """Put the stored clients into the cache and follow it from now on.

        Clients not listed within the retention window are dropped, unless
        they are in `keep`. Returns the MAC addresses dropped, so their
        entities can go too.
        """
        self._clients = clients
        now = dt_util.utcnow()
        pruned: list[str] = []
        for mac, stored in list(self._stored.items()):
            last_seen = dt_util.parse_datetime(stored["last_seen"] or "")
            if mac not in keep and (
                last_seen is None or now - last_seen > CLIENT_RESTORE_MAX_AGE
            ):
                pruned.append(mac)
                continue
            clients.restore(stored["raw"], last_seen)
        return pruned

    @callback
    def schedule_save(self, *_: Any) -> None:
        """Save the cache soon; one save covers a whole poll's updates."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, StoredClient]:
        """Every client in the cache, with when it was last listed."""
        assert self._clients is not None
        self._stored = {
            mac: StoredClient(
                raw=client.raw,
                last_seen=_isoformat(self._clients.last_seen(mac)),
            )
            for mac, client in self._clients.items()
        }
        return self._stored

    async def async_remove(self) -> None:
        """Delete the stored clients, when the entry is removed."""
        await self._store.async_remove()


def _isoformat(value: datetime | None) -> str | None:
    """ISO 8601, or None."""
    return value.isoformat() if value is not None else None
