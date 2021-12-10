"""Handle MySensors devices."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from mysensors import BaseAsyncGateway, Sensor
from mysensors.const_14 import MessageType, Stream
from mysensors.message import Message
from mysensors.ota import fw_hex_to_int
from mysensors.sensor import ChildSensor

from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    CHILD_CALLBACK,
    CONF_DEVICE,
    DOMAIN,
    NODE_CALLBACK,
    NODE_ROOT_CHILD_ID,
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
ATTR_FIRMWARE = "firmware"
ATTR_FIRMWARE_TYPE = "type"
ATTR_FIRMWARE_VERSION = "version"
ATTR_FIRMWARE_BLOCKS = "blocks"
ATTR_FIRMWARE_CRC = "crc"
ATTR_FIRMWARE_BOOTLOADER_VERSION = "bl_version"
ATTR_FIRMWARE_REQ_BLOCK = "req_block"
ATTR_FIRMWARE_REQ_TOTAL_BLOCKS = "req_total_blocks"

MYSENSORS_PLATFORM_DEVICES = "mysensors_devices_{}"


class MySensorsDevice:
    """Representation of a MySensors device."""

    hass: HomeAssistant

    def __init__(
        self,
        gateway_id: GatewayId,
        gateway: BaseAsyncGateway,
        node_id: int,
        child_id: int,
        value_type: int,
    ) -> None:
        """Set up the MySensors device."""
        self.gateway_id: GatewayId = gateway_id
        self.gateway: BaseAsyncGateway = gateway
        self.node_id: int = node_id
        self.child_id: int = child_id
        self.value_type: int = value_type  # value_type as int. string variant can be looked up in gateway consts
        self.child_type = self._child.type
        self._values: dict[int, Any] = {}
        self._update_scheduled = False
        self._firmware: dict[str, str] = {}

    @property
    def dev_id(self) -> DevId:
        """Return the DevId of this device.

        It is used to route incoming MySensors messages to the correct device/entity.
        """
        return self.gateway_id, self.node_id, self.child_id, self.value_type

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(f"{__name__}.{self.name}")

    async def async_will_remove_from_hass(self) -> None:
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
        if self.child_id == NODE_ROOT_CHILD_ID:
            return ChildSensor(
                child_id=NODE_ROOT_CHILD_ID, child_type=0, description="Node"
            )
        else:
            return self._node.children[self.child_id]

    @property
    def sketch_name(self) -> str:
        """Return the name of the sketch running on the whole node.

        The name will be the same for several entities.
        """
        return self._node.sketch_name  # type: ignore[no-any-return]

    @property
    def sketch_version(self) -> str:
        """Return the version of the sketch running on the whole node.

        The name will be the same for several entities.
        """
        return self._node.sketch_version  # type: ignore[no-any-return]

    @property
    def node_name(self) -> str:
        """Name of the whole node.

        The name will be the same for several entities.
        """
        return f"{self.sketch_name} {self.node_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for use in home assistant."""
        return f"{self.gateway_id}-{self.node_id}-{self.child_id}-{self.value_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.gateway_id}-{self.node_id}")},
            manufacturer="MySensors",
            model=self.sketch_name,
            name=self.node_name,
            sw_version=self.sketch_version,
            configuration_url=f"homeassistant://config/mysensors?config_entry={self.gateway_id}&nodeId={self.node_id}",
            #   via_device={(DOMAIN, self.gateway_id)}, # In future update the Gateway mut be a device itself
        )

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        child = self._child

        if child.description:
            return str(child.description)
        return f"{self.node_name} {self.child_id}"

    @property
    def _extra_attributes(self) -> dict[str, Any]:
        """Return device specific attributes."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        attr = {
            ATTR_BATTERY_LEVEL: node.battery_level,
            ATTR_HEARTBEAT: node.heartbeat,
            ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: child.description,
            ATTR_NODE_ID: self.node_id,
            ATTR_FIRMWARE: self._firmware,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            attr[set_req(value_type).name] = value

        return attr

    async def async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        if self.child_id == NODE_ROOT_CHILD_ID:
            return
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

    async def _async_update_callback(self) -> None:
        """Update the device."""
        raise NotImplementedError

    @callback
    def async_update_callback(self, msg: Message = None) -> None:
        """Update the device after delay."""
        if (
            msg is not None
            and msg.type == MessageType.stream
            and msg.sub_type == Stream.ST_FIRMWARE_CONFIG_REQUEST
        ):
            (
                self._firmware[ATTR_FIRMWARE_TYPE],
                self._firmware[ATTR_FIRMWARE_VERSION],
                self._firmware[ATTR_FIRMWARE_BLOCKS],
                self._firmware[ATTR_FIRMWARE_CRC],
                self._firmware[ATTR_FIRMWARE_BOOTLOADER_VERSION],
            ) = fw_hex_to_int(msg.payload, 5)
            _LOGGER.debug("Firmware Request:%s", self._firmware)
        elif (
            msg is not None
            and msg.type == MessageType.stream
            and msg.sub_type == Stream.ST_FIRMWARE_REQUEST
        ):
            (
                req_fw_type,
                req_fw_ver,
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
            ) = fw_hex_to_int(msg.payload, 3)
            self._firmware[ATTR_FIRMWARE_REQ_TOTAL_BLOCKS] = max(
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
                self._firmware.get(ATTR_FIRMWARE_REQ_TOTAL_BLOCKS, "0"),
            )
            _LOGGER.debug(
                "Received firmware request with firmware type %s, "
                "firmware version %s, block index %s / %s",
                req_fw_type,
                req_fw_ver,
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
                self._firmware.get(ATTR_FIRMWARE_REQ_TOTAL_BLOCKS, "0"),
            )
        if self._update_scheduled:
            return

        async def update() -> None:
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


def get_mysensors_devices(
    hass: HomeAssistant, domain: str
) -> dict[DevId, MySensorsDevice]:
    """Return MySensors devices for a hass platform name."""
    if MYSENSORS_PLATFORM_DEVICES.format(domain) not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_PLATFORM_DEVICES.format(domain)] = {}
    devices: dict[DevId, MySensorsDevice] = hass.data[DOMAIN][
        MYSENSORS_PLATFORM_DEVICES.format(domain)
    ]
    return devices


class MySensorsEntity(MySensorsDevice, Entity):
    """Representation of a MySensors entity."""

    @property
    def should_poll(self) -> bool:
        """Return the polling state. The gateway pushes its states."""
        return False

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return self.value_type in self._values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attr = self._extra_attributes

        assert self.platform
        assert self.platform.config_entry
        attr[ATTR_DEVICE] = self.platform.config_entry.data[CONF_DEVICE]

        return attr

    async def _async_update_callback(self) -> None:
        """Update the entity."""
        await self.async_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
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


# FIXME: Not yet used
class MySensorsNodeEntity(MySensorsEntity):
    """Rappresentation of a MySensor node."""

    def __init__(
        self,
        gateway_id: GatewayId,
        gateway: BaseAsyncGateway,
        node_id: int,
        child_id: int,
        value_type: int,
    ) -> None:
        """Set up the MySensors device."""
        super().__init__(gateway_id, gateway, node_id, child_id, value_type)
        self._firmware: dict[str, str] = {}

    @property
    def _extra_attributes(self) -> dict[str, Any]:
        """Return device specific attributes."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        attr = {
            ATTR_BATTERY_LEVEL: node.battery_level,
            ATTR_HEARTBEAT: node.heartbeat,
            ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: child.description,
            ATTR_NODE_ID: self.node_id,
            ATTR_FIRMWARE: self._firmware,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            attr[set_req(value_type).name] = value

        return attr

    @callback
    def async_update_callback(self, msg: Message = None) -> None:
        """Update the device after delay."""

        if (
            msg is not None
            and msg.type == MessageType.stream
            and msg.sub_type == Stream.ST_FIRMWARE_CONFIG_REQUEST
        ):
            (
                self._firmware[ATTR_FIRMWARE_TYPE],
                self._firmware[ATTR_FIRMWARE_VERSION],
                self._firmware[ATTR_FIRMWARE_BLOCKS],
                self._firmware[ATTR_FIRMWARE_CRC],
                self._firmware[ATTR_FIRMWARE_BOOTLOADER_VERSION],
            ) = fw_hex_to_int(msg.payload, 5)
            _LOGGER.debug("Firmware Request: %s", self._firmware)
        elif (
            msg is not None
            and msg.type == MessageType.stream
            and msg.sub_type == Stream.ST_FIRMWARE_REQUEST
        ):
            (
                req_fw_type,
                req_fw_ver,
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
            ) = fw_hex_to_int(msg.payload, 3)
            self._firmware[ATTR_FIRMWARE_REQ_TOTAL_BLOCKS] = max(
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
                self._firmware[ATTR_FIRMWARE_REQ_TOTAL_BLOCKS],
            )

            _LOGGER.info(
                "Received firmware request with firmware type %s, "
                "firmware version %s, block index %s / %s",
                req_fw_type,
                req_fw_ver,
                self._firmware[ATTR_FIRMWARE_REQ_BLOCK],
                self._firmware[ATTR_FIRMWARE_REQ_TOTAL_BLOCKS],
            )

        if self._update_scheduled:
            return

        async def update() -> None:
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
