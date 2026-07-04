"""Data update coordinator for the Duco integration."""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import cast, override

from duco_connectivity import DucoClient
from duco_connectivity.exceptions import (
    DucoConnectionError,
    DucoError,
    DucoResponseError,
)
from duco_connectivity.models import BoardInfo, Node, NodeListActionItemList, NodeName

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NODE_NAME_UPDATE_INTERVAL, SCAN_INTERVAL
from .validation import UnsupportedBoardError, async_get_supported_board_info

_LOGGER = logging.getLogger(__name__)

type DucoConfigEntry = ConfigEntry[DucoCoordinator]
type NodeNameUpdateCallback = Callable[[dict[int, str]], None]


@dataclass
class DucoData:
    """Data returned by the Duco coordinator."""

    nodes: dict[int, Node]
    node_actions: NodeListActionItemList
    rssi_wifi: int | None
    time_filter_remain: int | None


class DucoCoordinator(DataUpdateCoordinator[DucoData]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry
    board_info: BoardInfo
    mac: str
    _supports_time_filter_remain: bool
    _configured_node_names: dict[int, str]
    _known_node_names: dict[int, str]
    _last_node_name_refresh: datetime | None
    _node_name_update_callbacks: list[NodeNameUpdateCallback]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DucoConfigEntry,
        client: DucoClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._configured_node_names = {}
        self._last_node_name_refresh = None
        self.mac = cast(str, config_entry.unique_id)
        self._known_node_names = {}
        self._node_name_update_callbacks = []
        self._supports_time_filter_remain = True

    async def _async_refresh_node_names(self) -> None:
        """Refresh cached node names from Duco at most once per day."""
        now = dt_util.utcnow()
        if (
            self._last_node_name_refresh is not None
            and now - self._last_node_name_refresh < NODE_NAME_UPDATE_INTERVAL
        ):
            return

        self._last_node_name_refresh = now

        try:
            configured_node_names = await self.client.async_get_node_configs(
                parameter="Name"
            )
        except DucoError as err:
            _LOGGER.debug("Could not fetch Duco node names", exc_info=err)
            return

        self._configured_node_names = {
            node.node_id: node.name.value
            for node in configured_node_names.nodes
            if node.name is not None
        }

    @callback
    def async_add_node_name_listener(
        self, update_callback: NodeNameUpdateCallback
    ) -> CALLBACK_TYPE:
        """Listen for Duco node name changes."""
        self._node_name_update_callbacks.append(update_callback)

        @callback
        def remove_listener() -> None:
            """Remove the node name listener."""
            self._node_name_update_callbacks.remove(update_callback)

        return remove_listener

    @override
    async def _async_setup(self) -> None:
        """Fetch board info once during initial setup."""
        try:
            self.board_info = await async_get_supported_board_info(self.client)
        except UnsupportedBoardError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_board",
            ) from err
        except DucoResponseError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except DucoError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    @override
    async def _async_update_data(self) -> DucoData:
        """Fetch node data from the Duco box."""
        try:
            nodes = await self.client.async_get_nodes()
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except DucoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

        await self._async_refresh_node_names()

        if self._configured_node_names:
            nodes = [
                replace(
                    node,
                    general=replace(
                        node.general,
                        name=NodeName(
                            self._configured_node_names.get(
                                node.node_id, node.general.name
                            )
                        ),
                    ),
                )
                for node in nodes
            ]

        try:
            node_actions = await self.client.async_get_node_actions()
        except DucoError as err:
            previous_data = cast(DucoData | None, self.data)
            node_actions = (
                previous_data.node_actions
                if previous_data is not None
                else NodeListActionItemList(nodes=[])
            )
            _LOGGER.warning(
                "Could not fetch Duco node actions; %s",
                "keeping previous select discovery data"
                if previous_data is not None
                else "starting with empty select discovery data",
                exc_info=err,
            )

        # LAN info only backs the diagnostic RSSI sensor, so failures on this
        # supplemental endpoint, including connection failures, should not make
        # the primary node entities unavailable.
        rssi_wifi = self.data.rssi_wifi if self.data else None
        try:
            lan_info = await self.client.async_get_lan_info()
        except DucoError as err:
            _LOGGER.debug("Could not fetch Duco LAN info", exc_info=err)
        else:
            rssi_wifi = lan_info.rssi_wifi

        # Heat recovery info only backs the optional filter timer sensor, so
        # failures on this supplemental endpoint should not make the primary
        # node entities unavailable.
        time_filter_remain = None
        if self._supports_time_filter_remain:
            with suppress(DucoError):
                time_filter_remain = await self.client.async_get_time_filter_remaining()
                self._supports_time_filter_remain = time_filter_remain is not None

        data = DucoData(
            nodes={node.node_id: node for node in nodes},
            node_actions=node_actions,
            rssi_wifi=rssi_wifi,
            time_filter_remain=time_filter_remain,
        )

        current_node_names = {
            node_id: node.general.name or f"Node {node_id}"
            for node_id, node in data.nodes.items()
        }
        updated_node_names = {
            node_id: node_name
            for node_id, node_name in current_node_names.items()
            if self._known_node_names.get(node_id) != node_name
        }
        self._known_node_names = current_node_names

        if updated_node_names:
            for update_callback in self._node_name_update_callbacks:
                update_callback(updated_node_names)

        return data
