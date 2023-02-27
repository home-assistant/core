"""Support for Freebox base features."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


class FreeboxHomeBaseClass(Entity):
    """Representation of a Freebox base entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        router: FreeboxRouter,
        node: dict[str, Any],
        sub_node: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a Freebox entity."""
        self._hass = hass
        self._router = router
        self._node = node
        self._sub_node = sub_node
        self._id = node["id"]
        self._name = node["label"].strip()
        self._device_name = self._name
        self._unique_id = f"{self._router.mac}-node_{self._id}"

        if sub_node is not None:
            self._name += " " + sub_node["label"].strip()
            self._unique_id += "-" + sub_node["name"].strip()

        self._available = True
        self._firmware = node["props"].get("FwVersion")
        self._manufacturer = "Freebox SAS"
        self._model = ""
        self._remove_signal_update: Any

        if node["category"] == "pir":
            self._model = "F-HAPIR01A"
        elif node["category"] == "camera":
            self._model = "F-HACAM01A"
        elif node["category"] == "dws":
            self._model = "F-HADWS01A"
        elif node["category"] == "kfb":
            self._model = "F-HAKFB01A"
        elif node["category"] == "alarm":
            self._model = "F-MSEC07A"
        elif node["type"].get("inherit") == "node::rts":
            self._manufacturer = "Somfy"
            self._model = "RTS"
        elif node["type"].get("inherit") == "node::ios":
            self._manufacturer = "Somfy"
            self._model = "IOHome"

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._id)},
            "name": self._device_name,
            "manufacturer": self._manufacturer,
            "model": self._model,
            "sw_version": self._firmware,
        }

    async def async_update_signal(self):
        """Update signal."""
        self._node = self._router.home_devices[self._id]
        # Update name
        if self._sub_node is None:
            self._name = self._node["label"].strip()
        else:
            self._name = (
                self._node["label"].strip() + " " + self._sub_node["label"].strip()
            )
        self.async_write_ha_state()

    async def set_home_endpoint_value(self, command_id: Any, value=None) -> None:
        """Set Home endpoint value."""
        if value is None:
            value = {"value": None}
        if command_id is None:
            _LOGGER.error("Unable to SET a value through the API. Command is None")
            return
        await self._router.api.home.set_home_endpoint_value(
            self._id, command_id, {"value": value}
        )

    def get_command_id(self, nodes, name) -> int | None:
        """Get the command id."""
        node = next(
            filter(lambda x: (x["name"] == name), nodes),
            None,
        )
        if node is None:
            _LOGGER.warning("The Freebox Home device has no value for: %s", name)
            return None
        return node["id"]

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.remove_signal_update(
            async_dispatcher_connect(
                self._hass,
                self._router.signal_home_device_update,
                self.async_update_signal,
            )
        )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self._remove_signal_update()

    def remove_signal_update(self, dispacher: None):
        """Register state update callback."""
        self._remove_signal_update = dispacher
