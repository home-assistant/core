"""Data update coordinator for the Duco integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from duco_connectivity import DucoClient
from duco_connectivity.exceptions import (
    DucoConnectionError,
    DucoError,
    DucoResponseError,
)
from duco_connectivity.models import BoardInfo, InfoZonesOverview, Node

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .validation import UnsupportedBoardError, async_get_supported_board_info

_LOGGER = logging.getLogger(__name__)

type DucoConfigEntry = ConfigEntry[DucoCoordinator]
type NodeZoneGroup = tuple[int, int]


def _build_node_zone_groups(zones_info: InfoZonesOverview) -> dict[int, NodeZoneGroup]:
    """Return unique zone/group memberships per node.

    Nodes with no matches or multiple matches are omitted so callers only get
    deep-link metadata when the target is unambiguous.
    """
    node_memberships: dict[int, set[NodeZoneGroup]] = {}

    for zone in zones_info.zones:
        for group in zone.groups:
            zone_group = (zone.zone_id, group.group_id)
            for node_id in group.nodes:
                node_memberships.setdefault(node_id, set()).add(zone_group)

    return {
        node_id: next(iter(memberships))
        for node_id, memberships in node_memberships.items()
        if len(memberships) == 1
    }


@dataclass
class DucoData:
    """Data returned by the Duco coordinator."""

    nodes: dict[int, Node]
    rssi_wifi: int | None
    node_zone_groups: dict[int, NodeZoneGroup]


class DucoCoordinator(DataUpdateCoordinator[DucoData]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry
    board_info: BoardInfo

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
        self._zone_mapping_changed = False
        self._zone_mapping_listeners: list[CALLBACK_TYPE] = []

    @callback
    def async_add_zone_mapping_listener(
        self, update_callback: CALLBACK_TYPE
    ) -> Callable[[], None]:
        """Listen for zone mapping changes."""
        self._zone_mapping_listeners.append(update_callback)

        @callback
        def _remove_listener() -> None:
            self._zone_mapping_listeners.remove(update_callback)

        return _remove_listener

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
                translation_placeholders={"error": repr(err)},
            ) from err
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except DucoError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> DucoData:
        """Fetch node data from the Duco box."""
        try:
            nodes = await self.client.async_get_nodes()
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except DucoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": repr(err)},
            ) from err

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

        previous_node_zone_groups = self.data.node_zone_groups if self.data else {}
        node_zone_groups = previous_node_zone_groups
        try:
            node_zone_groups = _build_node_zone_groups(
                await self.client.async_get_zones_info()
            )
        except DucoConnectionError as err:
            _LOGGER.debug(
                "Could not fetch Duco zone membership info for subnode visit links: %s",
                err,
            )
        except DucoError as err:
            _LOGGER.debug(
                "Could not parse Duco zone membership info for subnode visit links: %s",
                err,
            )

        self._zone_mapping_changed = node_zone_groups != previous_node_zone_groups

        return DucoData(
            nodes={node.node_id: node for node in nodes},
            rssi_wifi=rssi_wifi,
            node_zone_groups=node_zone_groups,
        )

    @callback
    def _async_refresh_finished(self) -> None:
        """Handle a finished refresh."""
        if not self.last_update_success or not self._zone_mapping_changed:
            return

        for update_callback in list(self._zone_mapping_listeners):
            update_callback()
