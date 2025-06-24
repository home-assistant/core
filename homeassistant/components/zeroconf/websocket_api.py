"""The zeroconf integration websocket apis."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from itertools import chain
import logging
from typing import Any, cast

import voluptuous as vol
from zeroconf import BadTypeInNameException, DNSPointer, Zeroconf, current_time_millis
from zeroconf.asyncio import AsyncServiceInfo, IPVersion

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_bytes

from .const import DOMAIN, REQUEST_TIMEOUT
from .discovery import DATA_DISCOVERY, ZeroconfDiscovery
from .models import HaAsyncZeroconf

_LOGGER = logging.getLogger(__name__)
CLASS_IN = 1
TYPE_PTR = 12


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the zeroconf websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_discovery)


def serialize_service_info(service_info: AsyncServiceInfo) -> dict[str, Any]:
    """Serialize an AsyncServiceInfo object."""
    return {
        "name": service_info.name,
        "type": service_info.type,
        "port": service_info.port,
        "properties": service_info.decoded_properties,
        "ip_addresses": [
            str(ip) for ip in service_info.ip_addresses_by_version(IPVersion.All)
        ],
    }


class _DiscoverySubscription:
    """Class to hold and manage the subscription data."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        ws_msg_id: int,
        aiozc: HaAsyncZeroconf,
        discovery: ZeroconfDiscovery,
    ) -> None:
        """Initialize the subscription data."""
        self.hass = hass
        self.discovery = discovery
        self.aiozc = aiozc
        self.ws_msg_id = ws_msg_id
        self.connection = connection

    @callback
    def _async_unsubscribe(
        self, cancel_callbacks: tuple[Callable[[], None], ...]
    ) -> None:
        """Unsubscribe the callback."""
        for cancel_callback in cancel_callbacks:
            cancel_callback()

    async def async_start(self) -> None:
        """Start the subscription."""
        connection = self.connection
        listeners = (
            self.discovery.async_register_service_update_listener(
                self._async_on_update
            ),
            self.discovery.async_register_service_removed_listener(
                self._async_on_remove
            ),
        )
        connection.subscriptions[self.ws_msg_id] = partial(
            self._async_unsubscribe, listeners
        )
        self.connection.send_message(
            json_bytes(websocket_api.result_message(self.ws_msg_id))
        )
        await self._async_update_from_cache()

    async def _async_update_from_cache(self) -> None:
        """Load the records from the cache."""
        tasks: list[asyncio.Task[None]] = []
        now = current_time_millis()
        for record in self._async_get_ptr_records(self.aiozc.zeroconf):
            try:
                info = AsyncServiceInfo(record.name, record.alias)
            except BadTypeInNameException as ex:
                _LOGGER.debug(
                    "Ignoring record with bad type in name: %s: %s", record.alias, ex
                )
                continue
            if info.load_from_cache(self.aiozc.zeroconf, now):
                self._async_on_update(info)
            else:
                tasks.append(
                    self.hass.async_create_background_task(
                        self._async_handle_service(info),
                        f"zeroconf resolve {record.alias}",
                    ),
                )

        if tasks:
            await asyncio.gather(*tasks)

    def _async_get_ptr_records(self, zc: Zeroconf) -> list[DNSPointer]:
        """Return all PTR records for the HAP type."""
        return cast(
            list[DNSPointer],
            list(
                chain.from_iterable(
                    zc.cache.async_all_by_details(zc_type, TYPE_PTR, CLASS_IN)
                    for zc_type in self.discovery.zeroconf_types
                )
            ),
        )

    async def _async_handle_service(self, info: AsyncServiceInfo) -> None:
        """Add a device that became visible via zeroconf."""
        await info.async_request(self.aiozc.zeroconf, REQUEST_TIMEOUT)
        self._async_on_update(info)

    def _async_event_message(self, message: dict[str, Any]) -> None:
        self.connection.send_message(
            json_bytes(websocket_api.event_message(self.ws_msg_id, message))
        )

    def _async_on_update(self, info: AsyncServiceInfo) -> None:
        if info.type in self.discovery.zeroconf_types:
            self._async_event_message({"add": [serialize_service_info(info)]})

    def _async_on_remove(self, name: str) -> None:
        self._async_event_message({"remove": [{"name": name}]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "zeroconf/subscribe_discovery",
    }
)
@websocket_api.async_response
async def ws_subscribe_discovery(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe advertisements websocket command."""
    discovery = hass.data[DATA_DISCOVERY]
    aiozc: HaAsyncZeroconf = hass.data[DOMAIN]
    await _DiscoverySubscription(
        hass, connection, msg["id"], aiozc, discovery
    ).async_start()
