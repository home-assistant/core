"""Support for Freebox base features."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VALUE_NOT_SET
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
    def available(self):
        """Return True if entity is available."""
        return self._available

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
        # Update NAME
        if self._sub_node is None:
            self._name = self._node["label"].strip()
        else:
            self._name = (
                self._node["label"].strip() + " " + self._sub_node["label"].strip()
            )
        self.async_write_ha_state()

    async def set_home_endpoint_value(self, command_id, value=None):
        """Set Home endpoint value."""
        if value is None:
            value = {"value": None}
        if command_id == VALUE_NOT_SET:
            _LOGGER.error(
                "Unable to SET a value through the API. Command is VALUE_NOT_SET"
            )
            return False
        await self._router.api.home.set_home_endpoint_value(self._id, command_id, value)

    async def get_home_endpoint_value(self, command_id):
        """Get Home endpoint value."""
        if command_id == VALUE_NOT_SET:
            _LOGGER.error(
                "Unable to GET a value through the API. Command is VALUE_NOT_SET"
            )
            return VALUE_NOT_SET
        try:
            node = await self._router.api.home.get_home_endpoint_value(
                self._id, command_id
            )
        except TimeoutError:
            _LOGGER.warning("The Freebox API Timeout during a value retrieval")
            return VALUE_NOT_SET
        return node.get("value", VALUE_NOT_SET)

    def get_command_id(self, nodes, ep_type, name):
        """Get the command id."""
        node = next(
            filter(lambda x: (x["name"] == name and x["ep_type"] == ep_type), nodes),
            None,
        )
        if node is None:
            _LOGGER.warning(
                "The Freebox Home device has no value for: " + ep_type + "/" + name
            )
            return VALUE_NOT_SET
        return node["id"]

    def get_value(self, ep_type, name):
        """Get the value."""
        node = next(
            filter(
                lambda x: (x["name"] == name and x["ep_type"] == ep_type),
                self._node["show_endpoints"],
            ),
            None,
        )
        if node is None:
            _LOGGER.warning(
                "The Freebox Home device has no node for: " + ep_type + "/" + name
            )
            return VALUE_NOT_SET
        return node.get("value", VALUE_NOT_SET)

    async def async_set_value(self, ep_type, name, value):
        """Set the value."""
        node = next(
            filter(
                lambda x: (x["name"] == name and x["ep_type"] == ep_type),
                self._node["show_endpoints"],
            ),
            None,
        )
        if node is None:
            _LOGGER.warning(
                "The Freebox Home device has no node for: " + ep_type + "/" + name
            )
            return
        node["value"] = value
        self.async_write_ha_state()

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
