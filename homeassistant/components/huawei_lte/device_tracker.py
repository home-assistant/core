"""Support for device tracking of Huawei LTE routers."""

import asyncio
import logging
import re
from typing import Any, Dict

import attr
from stringcase import snakecase

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.const import CONF_URL
from . import HuaweiLteBaseEntity
from .const import DOMAIN, KEY_WLAN_HOST_LIST


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.data[CONF_URL]]
    try:
        hosts = router.data[KEY_WLAN_HOST_LIST]["Hosts"]["Host"]
    except (KeyError, TypeError):
        _LOGGER.debug("%s[%s][%s] not in data", KEY_WLAN_HOST_LIST, "Hosts", "Host")
        return

    entities = []
    for host in (x for x in hosts if x.get("MacAddress")):
        entities.append(HuaweiLteScannerEntity(router, host["MacAddress"]))
    async_add_entities(entities)


def _better_snakecase(s: str) -> str:
    if s == s.upper():
        # All uppercase to all lowercase to get http for HTTP, not h_t_t_p
        s = s.lower()
    else:
        # Three or more consecutive uppercase with middle part lowercased
        # to get http_response for HTTPResponse, not h_t_t_p_response
        s = re.sub(
            r"([A-Z])([A-Z]+)([A-Z](?:[^A-Z]|$))",
            lambda match: f"{match.group(1)}{match.group(2).lower()}{match.group(3)}",
            s,
        )
    return snakecase(s)


@attr.s
class HuaweiLteScannerEntity(HuaweiLteBaseEntity, ScannerEntity):
    """Huawei LTE router scanner entity."""

    mac: str = attr.ib()

    _is_connected: bool = attr.ib(init=False, default=False)
    _name: str = attr.ib(init=False, default="device")
    _device_state_attributes: Dict[str, Any] = attr.ib(init=False, factory=dict)

    def __attrs_post_init__(self):
        """Set up internal state on init."""
        asyncio.run_coroutine_threadsafe(self.async_update(), self.router.hass.loop)

    @property
    def _entity_name(self) -> str:
        return self._name

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
    def device_state_attributes(self) -> Dict[str, Any]:
        """Get additional attributes related to entity state."""
        return self._device_state_attributes

    async def async_update(self) -> None:
        """Update state."""
        try:
            hosts = self.router.data[KEY_WLAN_HOST_LIST]["Hosts"]["Host"]
        except KeyError:
            _LOGGER.debug("%s[Hosts][Host] not in data", self.key)
            self._available = False
            return
        self._available = True

        host = next((x for x in hosts if x.get("MacAddress") == self.mac), None)
        self._is_connected = host is not None
        if self._is_connected:
            self._name = host.get("HostName", self.mac)
            self._device_state_attributes = {
                _better_snakecase(k): v
                for k, v in host.items()
                if k not in ("MacAddress", "HostName")
            }


def get_scanner(*args, **kwargs):
    """Old no longer used way to set up Huawei LTE device tracker."""
    _LOGGER.warning(
        "Loading and configuring as a platform is no longer supported or "
        "required, convert to enabling/disabling available entities"
    )
