"""Support for device tracking of Huawei LTE routers."""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, cast

import attr
from stringcase import snakecase

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import HuaweiLteBaseEntity, Router
from .const import DOMAIN, KEY_LAN_HOST_INFO, KEY_WLAN_HOST_LIST, UPDATE_SIGNAL

_LOGGER = logging.getLogger(__name__)

_DEVICE_SCAN = f"{DEVICE_TRACKER_DOMAIN}/device_scan"

_HostType = Dict[str, Any]


def _get_hosts(
    router: Router, ignore_subscriptions: bool = False
) -> list[_HostType] | None:
    for key in KEY_LAN_HOST_INFO, KEY_WLAN_HOST_LIST:
        if not ignore_subscriptions and key not in router.subscriptions:
            continue
        try:
            return cast(List[_HostType], router.data[key]["Hosts"]["Host"])
        except KeyError:
            _LOGGER.debug("%s[%s][%s] not in data", key, "Hosts", "Host")
    return None


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up from config entry."""

    # Grab hosts list once to examine whether the initial fetch has got some data for
    # us, i.e. if wlan host list is supported. Only set up a subscription and proceed
    # with adding and tracking entities if it is.
    router = hass.data[DOMAIN].routers[config_entry.data[CONF_URL]]
    if _get_hosts(router, True) is None:
        return

    # Initialize already tracked entities
    tracked: set[str] = set()
    registry = await entity_registry.async_get_registry(hass)
    known_entities: list[Entity] = []
    for entity in registry.entities.values():
        if (
            entity.domain == DEVICE_TRACKER_DOMAIN
            and entity.config_entry_id == config_entry.entry_id
        ):
            tracked.add(entity.unique_id)
            known_entities.append(
                HuaweiLteScannerEntity(router, entity.unique_id.partition("-")[2])
            )
    async_add_entities(known_entities, True)

    # Tell parent router to poll hosts list to gather new devices
    router.subscriptions[KEY_LAN_HOST_INFO].add(_DEVICE_SCAN)
    router.subscriptions[KEY_WLAN_HOST_LIST].add(_DEVICE_SCAN)

    async def _async_maybe_add_new_entities(url: str) -> None:
        """Add new entities if the update signal comes from our router."""
        if url == router.url:
            async_add_new_entities(hass, url, async_add_entities, tracked)

    # Register to handle router data updates
    disconnect_dispatcher = async_dispatcher_connect(
        hass, UPDATE_SIGNAL, _async_maybe_add_new_entities
    )
    router.unload_handlers.append(disconnect_dispatcher)

    # Add new entities from initial scan
    async_add_new_entities(hass, router.url, async_add_entities, tracked)


def _is_wireless(host: _HostType) -> bool:
    # LAN host info entries have an "InterfaceType" property, "Ethernet" / "Wireless".
    # WLAN host list ones don't, but they're expected to be all wireless.
    return cast(str, host.get("InterfaceType", "Wireless")) != "Ethernet"


def _is_connected(host: _HostType | None) -> bool:
    # LAN host info entries have an "Active" property, "1" or "0".
    # WLAN host list ones don't, but that call appears to return active hosts only.
    return False if host is None else cast(str, host.get("Active", "1")) != "0"


@callback
def async_add_new_entities(
    hass: HomeAssistantType,
    router_url: str,
    async_add_entities: Callable[[list[Entity], bool], None],
    tracked: set[str],
) -> None:
    """Add new entities that are not already being tracked."""
    router = hass.data[DOMAIN].routers[router_url]
    hosts = _get_hosts(router)
    if not hosts:
        return

    new_entities: list[Entity] = []
    for host in (
        x for x in hosts if _is_connected(x) and _is_wireless(x) and x.get("MacAddress")
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


@attr.s
class HuaweiLteScannerEntity(HuaweiLteBaseEntity, ScannerEntity):
    """Huawei LTE router scanner entity."""

    mac: str = attr.ib()

    _is_connected: bool = attr.ib(init=False, default=False)
    _hostname: str | None = attr.ib(init=False, default=None)
    _extra_state_attributes: dict[str, Any] = attr.ib(init=False, factory=dict)

    def __attrs_post_init__(self) -> None:
        """Initialize internal state."""
        self._extra_state_attributes["mac_address"] = self.mac

    @property
    def _entity_name(self) -> str:
        return self._hostname or self.mac

    @property
    def _device_unique_id(self) -> str:
        return self.mac

    @property
    def source_type(self) -> str:
        """Return SOURCE_TYPE_ROUTER."""
        return SOURCE_TYPE_ROUTER

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
        hosts = _get_hosts(self.router)
        if hosts is None:
            self._available = False
            return
        self._available = True
        host = next((x for x in hosts if x.get("MacAddress") == self.mac), None)
        self._is_connected = _is_connected(host)
        if host is not None:
            self._hostname = host.get("HostName")
            self._extra_state_attributes = {
                _better_snakecase(k): v
                for k, v in host.items()
                if k not in ("Active", "HostName")
            }
