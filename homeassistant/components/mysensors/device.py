"""Handle MySensors devices."""
from __future__ import annotations

from functools import partial
import logging

from mysensors import BaseAsyncGateway, Sensor
from mysensors.sensor import ChildSensor

from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    CHILD_CALLBACK,
    CONF_DEVICE,
    DOMAIN,
    NODE_CALLBACK,
    PLATFORM_TYPES,
    UPDATE_DELAY,
    DevId,
    GatewayId,
)

_LOGGER = logging.getLogger(__name__)

ATTR_CHILD_ID = "child_id"
ATTR_DESCRIPTION = "description"
ATTR_DEVICE = "device"
ATTR_NODE_ID = "node_id"
ATTR_HEARTBEAT = "heartbeat"
MYSENSORS_PLATFORM_DEVICES = "mysensors_devices_{}"


class MySensorsDevice:
    """Representation of a MySensors device."""

    def __init__(
        self,
        gateway_id: GatewayId,
        gateway: BaseAsyncGateway,
        node_id: int,
        child_id: int,
        value_type: int,
    ):
        """Set up the MySensors device."""
        self.gateway_id: GatewayId = gateway_id
        self.gateway: BaseAsyncGateway = gateway
        self.node_id: int = node_id
        self.child_id: int = child_id
        self.value_type: int = value_type  # value_type as int. string variant can be looked up in gateway consts
        self.child_type = self._child.type
        self._values = {}
        self._update_scheduled = False
        self.hass = None

    @property
    def dev_id(self) -> DevId:
        """Return the DevId of this device.

        It is used to route incoming MySensors messages to the correct device/entity.
        """
        return self.gateway_id, self.node_id, self.child_id, self.value_type

    @property
    def _logger(self):
        return logging.getLogger(f"{__name__}.{self.name}")

    async def async_will_remove_from_hass(self):
        """Remove this entity from home assistant."""
        for platform in PLATFORM_TYPES:
            platform_str = MYSENSORS_PLATFORM_DEVICES.format(platform)
            if platform_str in self.hass.data[DOMAIN]:
                platform_dict = self.hass.data[DOMAIN][platform_str]
                if self.dev_id in platform_dict:
                    del platform_dict[self.dev_id]
                    self._logger.debug(
                        "deleted %s from platform %s", self.dev_id, platform
                    )

    @property
    def _node(self) -> Sensor:
        return self.gateway.sensors[self.node_id]

    @property
    def _child(self) -> ChildSensor:
        return self._node.children[self.child_id]

    @property
    def sketch_name(self) -> str:
        """Return the name of the sketch running on the whole node (will be the same for several entities!)."""
        return self._node.sketch_name

    @property
    def sketch_version(self) -> str:
        """Return the version of the sketch running on the whole node (will be the same for several entities!)."""
        return self._node.sketch_version

    @property
    def node_name(self) -> str:
        """Name of the whole node (will be the same for several entities!)."""
        return f"{self.sketch_name} {self.node_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for use in home assistant."""
        return f"{self.gateway_id}-{self.node_id}-{self.child_id}-{self.value_type}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a dict that allows home assistant to puzzle all entities belonging to a node together."""
        return {
            "identifiers": {(DOMAIN, f"{self.gateway_id}-{self.node_id}")},
            "name": self.node_name,
            "manufacturer": DOMAIN,
            "sw_version": self.sketch_version,
        }

    @property
    def name(self):
        """Return the name of this entity."""
        return f"{self.node_name} {self.child_id}"

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        attr = {
            ATTR_BATTERY_LEVEL: node.battery_level,
            ATTR_HEARTBEAT: node.heartbeat,
            ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: child.description,
            ATTR_NODE_ID: self.node_id,
        }
        # This works when we are actually an Entity (i.e. all platforms except device_tracker)
        if hasattr(self, "platform"):
            # pylint: disable=no-member
            attr[ATTR_DEVICE] = self.platform.config_entry.data[CONF_DEVICE]

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            attr[set_req(value_type).name] = value

        return attr

    async def async_update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        set_req = self.gateway.const.SetReq
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "Entity update: %s: value_type %s, value = %s",
                self.name,
                value_type,
                value,
            )
            if value_type in (
                set_req.V_ARMED,
                set_req.V_LIGHT,
                set_req.V_LOCK_STATUS,
                set_req.V_TRIPPED,
                set_req.V_UP,
                set_req.V_DOWN,
                set_req.V_STOP,
            ):
                self._values[value_type] = STATE_ON if int(value) == 1 else STATE_OFF
            elif value_type == set_req.V_DIMMER:
                self._values[value_type] = int(value)
            else:
                self._values[value_type] = value

    async def _async_update_callback(self):
        """Update the device."""
        raise NotImplementedError

    @callback
    def async_update_callback(self):
        """Update the device after delay."""
        if self._update_scheduled:
            return

        async def update():
            """Perform update."""
            try:
                await self._async_update_callback()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error updating %s", self.name)
            finally:
                self._update_scheduled = False

        self._update_scheduled = True
        delayed_update = partial(self.hass.async_create_task, update())
        self.hass.loop.call_later(UPDATE_DELAY, delayed_update)


def get_mysensors_devices(hass, domain: str) -> dict[DevId, MySensorsDevice]:
    """Return MySensors devices for a hass platform name."""
    if MYSENSORS_PLATFORM_DEVICES.format(domain) not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_PLATFORM_DEVICES.format(domain)] = {}
    return hass.data[DOMAIN][MYSENSORS_PLATFORM_DEVICES.format(domain)]


class MySensorsEntity(MySensorsDevice, Entity):
    """Representation of a MySensors entity."""

    @property
    def should_poll(self):
        """Return the polling state. The gateway pushes its states."""
        return False

    @property
    def available(self):
        """Return true if entity is available."""
        return self.value_type in self._values

    async def _async_update_callback(self):
        """Update the entity."""
        await self.async_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                CHILD_CALLBACK.format(*self.dev_id),
                self.async_update_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                NODE_CALLBACK.format(self.gateway_id, self.node_id),
                self.async_update_callback,
            )
        )
