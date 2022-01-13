"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

import logging
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
    CoverEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, HOME_NODES_COVERS
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the covers."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        if home_node["category"] == "shutter":
            entities.append(
                FreeboxHomeNodeCover(
                    router,
                    home_node,
                    HOME_NODES_COVERS["shutter"],
                )
            )

    async_add_entities(entities, True)


class FreeboxCover(CoverEntity):
    """Representation of a Freebox cover."""

    _attr_should_poll = False

    def __init__(
        self,
        router: FreeboxRouter,
        description: CoverEntityDescription,
        unik: Any,
    ) -> None:
        """Initialize a Freebox cover."""
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox cover."""
        # state = self._router.sensors[self.entity_description.key]
        # self._attr = state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )


class FreeboxHomeNodeCover(FreeboxCover):
    """Representation of a Freebox Home node cover."""

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        description: CoverEntityDescription,
    ) -> None:
        """Initialize a Freebox Home node sensor."""
        super().__init__(router, description, home_node["id"])
        self._home_node = home_node
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = (
            f"{self._router.mac} {description.key} {self._home_node['id']}"
        )
        self._attr_supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        )

        self._position = None
        # Discover for set/get endpoints
        for endpoint in home_node.get("show_endpoints"):
            if endpoint["name"] == "position_set":
                if endpoint["ep_type"] == "signal":
                    self._get_endpoint_id = endpoint["id"]
                elif endpoint["ep_type"] == "slot":
                    self._set_endpoint_id = endpoint["id"]
            elif endpoint["name"] == "stop" and endpoint["ep_type"] == "slot":
                self._stop_endpoint_id = endpoint["id"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=f'{self._home_node["category"]}',
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            vendor_name="Freebox SAS",
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """Refresh position and state."""
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if end_point["id"] == self._get_endpoint_id:
                    self._position = 100 - end_point["value"]
        return self._position == 0

    @property
    def current_cover_position(self):
        """Return if the current cover position."""
        return self._position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._position == 0

    async def set_position(self, position):
        """Set the cover position from 0 (closed) to 100 (open)."""
        value_position = {"value": (100 - position)}
        try:
            await self._router.api.home.set_home_endpoint_value(
                self._home_node["id"], self._set_endpoint_id, value_position
            )
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )

    async def get_position(self):
        """Get the cover position from 0 (closed) to 100 (open)."""
        try:
            ret = await self._router.api.home.get_home_endpoint_value(
                self._home_node["id"], self._get_endpoint_id
            )
            self._position = 100 - ret["value"]
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )
        print(f"get_position -> {self._position}")
        return self._position

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.set_position(0)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        await self.set_position(100)
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Set cover position."""
        await self.set_position(kwargs.get(ATTR_POSITION))
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the current cover move."""
        try:
            await self._router.api.home.set_home_endpoint_value(
                self._home_node["id"], self._stop_endpoint_id, {"value": True}
            )
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
            )
