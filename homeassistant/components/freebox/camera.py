"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import DEFAULT_CONTENT_TYPE
from homeassistant.components.generic.camera import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_NAME,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    CONF_VERIFY_SSL,
    GenericCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the camera."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )
    for home_node in router.home_nodes.values():
        if home_node["category"] == "camera":
            entities.append(
                FreeboxHomeNodeCamera(
                    hass,
                    router,
                    home_node,
                )
            )

    async_add_entities(entities, True)


class FreeBoxCamera(GenericCamera):
    """Representation of a Freebox camera."""

    def __init__(self, hass, router, home_node):
        """Initialize as a subclass of GenericCamera."""
        props = home_node["props"]
        config = {
            CONF_NAME: "camera",
            CONF_STREAM_SOURCE: template.Template(
                f'http://{props["Login"]}:{props["Pass"]}@{props["Ip"]}/img/stream.m3u8'
            ),
            CONF_STILL_IMAGE_URL: template.Template(
                f'http://{props["Login"]}:{props["Pass"]}@{props["Ip"]}/img/snapshot.cgi?size=4&quality=1'
            ),
            CONF_VERIFY_SSL: True,
            CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
            CONF_FRAMERATE: 2,
            CONF_CONTENT_TYPE: DEFAULT_CONTENT_TYPE,
        }
        super().__init__(hass, config)
        self._router = router
        self._home_node = home_node
        self._attr_unique_id = f"{router.mac} camera {home_node['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info


class FreeboxHomeNodeCamera(FreeBoxCamera):
    """Representation of a Freebox Home node camera."""

    def __init__(
        self,
        hass: Any,
        router: FreeboxRouter,
        home_node: dict[str, Any],
    ) -> None:
        """Initialize a Freebox Home node camera."""
        super().__init__(hass, router, home_node)
        self._home_node = home_node
        self._attr_name = f"{home_node['label']}"
        self._unique_id = f"{self._router.mac} camera {self._home_node['id']}"

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
