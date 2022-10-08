"""Support for device tracking of Huawei LTE routers."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any, cast

from stringcase import snakecase

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HuaweiLteBaseEntity, Router
from .const import (
    CONF_TRACK_WIRED_CLIENTS,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DOMAIN,
    KEY_LAN_HOST_INFO,
    KEY_WLAN_HOST_LIST,
    UPDATE_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)

_DEVICE_SCAN = f"{DEVICE_TRACKER_DOMAIN}/device_scan"

_HostType = dict[str, Any]


def _get_hosts(
    router: Router, ignore_subscriptions: bool = False
) -> list[_HostType] | None:
    for key in KEY_LAN_HOST_INFO, KEY_WLAN_HOST_LIST:
        if not ignore_subscriptions and key not in router.subscriptions:
            continue
        try:
            return cast(list[_HostType], router.data[key]["Hosts"]["Host"])
        except KeyError:
            _LOGGER.debug("%s[%s][%s] not in data", key, "Hosts", "Host")
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""

    # Grab hosts list once to examine whether the initial fetch has got some data for
    # us, i.e. if wlan host list is supported. Only set up a subscription and proceed
    # with adding and tracking entities if it is.
    router = hass.data[DOMAIN].routers[config_entry.unique_id]
    if (hosts := _get_hosts(router, True)) is None:
        return

    # Initialize already tracked entities
    tracked: set[str] = set()
    registry = entity_registry.async_get(hass)
    known_entities: list[Entity] = []
    track_wired_clients = router.config_entry.options.get(
        CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
    )
    for entity in registry.entities.values():
        if (
            entity.domain == DEVICE_TRACKER_DOMAIN
            and entity.config_entry_id == config_entry.entry_id
        ):
            mac = entity.unique_id.partition("-")[2]
            # Do not add known wired clients if not tracking them (any more)
            skip = False
            if not track_wired_clients:
                for host in hosts:
                    if host.get("MacAddress") == mac:
                        skip = not _is_wireless(host)
                        break
            if not skip:
                tracked.add(entity.unique_id)
                known_entities.append(HuaweiLteScannerEntity(router, mac))
    async_add_entities(known_entities, True)

    # Tell parent router to poll hosts list to gather new devices
    router.subscriptions[KEY_LAN_HOST_INFO].add(_DEVICE_SCAN)
    router.subscriptions[KEY_WLAN_HOST_LIST].add(_DEVICE_SCAN)

    async def _async_maybe_add_new_entities(unique_id: str) -> None:
        """Add new entities if the update signal comes from our router."""
        if config_entry.unique_id == unique_id:
            async_add_new_entities(router, async_add_entities, tracked)

    # Register to handle router data updates
    disconnect_dispatcher = async_dispatcher_connect(
        hass, UPDATE_SIGNAL, _async_maybe_add_new_entities
    )
    config_entry.async_on_unload(disconnect_dispatcher)

    # Add new entities from initial scan
    async_add_new_entities(router, async_add_entities, tracked)


def _is_wireless(host: _HostType) -> bool:
    # LAN host info entries have an "InterfaceType" property, "Ethernet" / "Wireless".
    # WLAN host list ones don't, but they're expected to be all wireless.
    return cast(str, host.get("InterfaceType", "Wireless")) != "Ethernet"


def _is_connected(host: _HostType | None) -> bool:
    # LAN host info entries have an "Active" property, "1" or "0".
    # WLAN host list ones don't, but that call appears to return active hosts only.
    return False if host is None else cast(str, host.get("Active", "1")) != "0"


def _is_us(host: _HostType) -> bool:
    """Try to determine if the host entry is us, the HA instance."""
    # LAN host info entries have an "isLocalDevice" property, "1" / "0"; WLAN host list ones don't.
    return cast(str, host.get("isLocalDevice", "0")) == "1"


@callback
def async_add_new_entities(
    router: Router,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new entities that are not already being tracked."""
    if not (hosts := _get_hosts(router)):
        return

    track_wired_clients = router.config_entry.options.get(
        CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
    )

    new_entities: list[Entity] = []
    for host in (
        x
        for x in hosts
        if not _is_us(x)
        and _is_connected(x)
        and x.get("MacAddress")
        and (track_wired_clients or _is_wireless(x))
    ):
        entity = HuaweiLteScannerEntity(router, host["MacAddress"])
        if entity.unique_id in tracked:
            continue
        tracked.add(entity.unique_id)
        new_entities.append(entity)
    async_add_entities(new_entities, True)


def _better_snakecase(text: str) -> str:
    # Awaiting https://github.com/okunishinishi/python-stringcase/pull/18
    if text == text.upper():
        # All uppercase to all lowercase to get http for HTTP, not h_t_t_p
        text = text.lower()
    else:
        # Three or more consecutive uppercase with middle part lowercased
        # to get http_response for HTTPResponse, not h_t_t_p_response
        text = re.sub(
            r"([A-Z])([A-Z]+)([A-Z](?:[^A-Z]|$))",
            lambda match: f"{match.group(1)}{match.group(2).lower()}{match.group(3)}",
            text,
        )
    return cast(str, snakecase(text))


@dataclass
class HuaweiLteScannerEntity(HuaweiLteBaseEntity, ScannerEntity):
    """Huawei LTE router scanner entity."""

    _mac_address: str

    _ip_address: str | None = field(default=None, init=False)
    _is_connected: bool = field(default=False, init=False)
    _hostname: str | None = field(default=None, init=False)
    _extra_state_attributes: dict[str, Any] = field(default_factory=dict, init=False)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.hostname or self.mac_address

    @property
    def _device_unique_id(self) -> str:
        return self.mac_address

    @property
    def source_type(self) -> SourceType:
        """Return SourceType.ROUTER."""
        return SourceType.ROUTER

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._hostname

    @property
    def is_connected(self) -> bool:
        """Get whether the entity is connected."""
        return self._is_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get additional attributes related to entity state."""
        return self._extra_state_attributes

    async def async_update(self) -> None:
        """Update state."""
        if (hosts := _get_hosts(self.router)) is None:
            self._available = False
            return
        self._available = True
        host = next(
            (x for x in hosts if x.get("MacAddress") == self._mac_address), None
        )
        self._is_connected = _is_connected(host)
        if host is not None:
            # IpAddress can contain multiple semicolon separated addresses.
            # Pick one for model sanity; e.g. the dhcp component to which it is fed, parses and expects to see just one.
            self._ip_address = (host.get("IpAddress") or "").split(";", 2)[0] or None
            self._hostname = host.get("HostName")
            self._extra_state_attributes = {
                _better_snakecase(k): v
                for k, v in host.items()
                if k
                in {
                    "AddressSource",
                    "AssociatedSsid",
                    "InterfaceType",
                }
            }
