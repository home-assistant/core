"""Data update coordinator for the Duco integration."""

from contextlib import suppress
from dataclasses import dataclass, replace
import logging
from typing import cast, override

from duco_connectivity import DucoClient
from duco_connectivity.exceptions import (
    DucoConnectionError,
    DucoError,
    DucoResponseError,
)
from duco_connectivity.models import (
    BoardInfo,
    BypassSupplyTemperatureTarget,
    Node,
    NodeListActionItemList,
    NodeName,
    VentilationTemperatureInfo,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .validation import UnsupportedBoardError, async_get_supported_board_info

_LOGGER = logging.getLogger(__name__)


type DucoConfigEntry = ConfigEntry[DucoCoordinator]


@dataclass(slots=True, kw_only=True)
class DucoData:
    """Data returned by the Duco coordinator."""

    nodes: dict[int, Node]
    node_actions: NodeListActionItemList
    rssi_wifi: int | None
    time_filter_remain: int | None
    ventilation_temperatures: VentilationTemperatureInfo | None
    bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget]


class DucoCoordinator(DataUpdateCoordinator[DucoData]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry
    board_info: BoardInfo
    _configured_node_names: dict[int, str]
    _coordinator_update_version: int
    _node_refresh_versions: dict[int, int]
    _node_update_errors: dict[int, DucoError]
    _node_update_versions: dict[int, int]

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
        self._coordinator_update_version = 0
        self._node_refresh_versions = {}
        self._node_update_errors = {}
        self._node_update_versions = {}

    async def async_refresh_node(self, node_id: int) -> None:
        """Refresh one node and publish its latest reported state."""
        coordinator_update_version = self._coordinator_update_version
        refresh_version = self._node_refresh_versions.get(node_id, 0) + 1
        self._node_refresh_versions[node_id] = refresh_version

        try:
            node = await self.client.async_get_node_info(node_id)
        except DucoError as err:
            if (
                self._coordinator_update_version == coordinator_update_version
                and self._node_refresh_versions[node_id] == refresh_version
            ):
                self._node_update_errors[node_id] = err
                self._node_update_versions[node_id] = (
                    self._node_update_versions.get(node_id, 0) + 1
                )
                self.async_set_update_error(err)
            return

        # Do not publish stale readbacks or mask a concurrent coordinator failure.
        if (
            self._coordinator_update_version != coordinator_update_version
            or self._node_refresh_versions[node_id] != refresh_version
            or not self.last_update_success
        ):
            return

        if (current_node := self.data.nodes.get(node_id)) is None:
            return

        node = replace(
            node,
            general=replace(
                node.general,
                name=current_node.general.name,
            ),
        )
        self._node_update_versions[node_id] = (
            self._node_update_versions.get(node_id, 0) + 1
        )
        self._node_update_errors.pop(node_id, None)
        self.async_set_updated_data(
            replace(
                self.data,
                nodes={**self.data.nodes, node_id: node},
            )
        )

    async def _async_load_node_names(self) -> None:
        """Load configured Duco node names during setup."""
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

        await self._async_load_node_names()

    @override
    async def _async_update_data(self) -> DucoData:
        """Fetch node data from the Duco box."""
        node_update_versions = self._node_update_versions.copy()
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

        nodes_by_id = {node.node_id: node for node in nodes}

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
        # node entities unavailable. A None result leaves the sensor absent
        # but keeps the helper pollable so data can appear on a later refresh.
        time_filter_remain = None
        with suppress(DucoError):
            time_filter_remain = await self.client.async_get_time_filter_remaining()

        ventilation_temperatures = (
            self.data.ventilation_temperatures if self.data else None
        )
        try:
            ventilation_temperatures = (
                await self.client.async_get_ventilation_temperature_info()
            )
        except DucoError as err:
            _LOGGER.debug("Could not fetch Duco ventilation temperatures", exc_info=err)

        bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget] = {}
        try:
            bypass_supply_temperature_targets = (
                await self.client.async_get_bypass_supply_temperature_targets()
            )
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

        # The bulk node response may predate a write completed during this poll.
        if self.data is not None:
            for node_id, version in self._node_update_versions.items():
                if node_update_versions.get(node_id) == version:
                    continue
                if node_update_error := self._node_update_errors.get(node_id):
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key=(
                            "cannot_connect"
                            if isinstance(node_update_error, DucoConnectionError)
                            else "api_error"
                        ),
                    ) from node_update_error
                if node_id in nodes_by_id and node_id in self.data.nodes:
                    nodes_by_id[node_id] = self.data.nodes[node_id]

            self._coordinator_update_version += 1
        return DucoData(
            nodes=nodes_by_id,
            node_actions=node_actions,
            rssi_wifi=rssi_wifi,
            time_filter_remain=time_filter_remain,
            ventilation_temperatures=ventilation_temperatures,
            bypass_supply_temperature_targets=bypass_supply_temperature_targets,
        )
