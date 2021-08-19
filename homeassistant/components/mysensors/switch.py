"""Support for MySensors switches."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import mysensors
from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...config_entries import ConfigEntry
from ...helpers.dispatcher import async_dispatcher_connect
from .const import (
    DOMAIN as MYSENSORS_DOMAIN,
    MYSENSORS_DISCOVERY,
    SERVICE_SEND_IR_CODE,
    DiscoveryInfo,
    SensorType,
)
from .device import MySensorsDevice
from .helpers import on_unload

ATTR_IR_CODE = "V_IR_SEND"

SEND_IR_CODE_SERVICE_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_ENTITY_ID): cv.entity_ids, vol.Required(ATTR_IR_CODE): cv.string}
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""
    device_class_map: dict[SensorType, type[MySensorsDevice]] = {
        "S_DOOR": MySensorsSwitch,
        "S_MOTION": MySensorsSwitch,
        "S_SMOKE": MySensorsSwitch,
        "S_LIGHT": MySensorsSwitch,
        "S_LOCK": MySensorsSwitch,
        "S_IR": MySensorsIRSwitch,
        "S_BINARY": MySensorsSwitch,
        "S_SPRINKLER": MySensorsSwitch,
        "S_WATER_LEAK": MySensorsSwitch,
        "S_SOUND": MySensorsSwitch,
        "S_VIBRATION": MySensorsSwitch,
        "S_MOISTURE": MySensorsSwitch,
        "S_WATER_QUALITY": MySensorsSwitch,
    }

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors switch."""
        mysensors.setup_mysensors_platform(
            hass,
            DOMAIN,
            discovery_info,
            device_class_map,
            async_add_entities=async_add_entities,
        )

    async def async_send_ir_code_service(service: ServiceCall) -> None:
        """Set IR code as device state attribute."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        ir_code = service.data.get(ATTR_IR_CODE)
        devices = mysensors.get_mysensors_devices(hass, DOMAIN)

        if entity_ids:
            _devices = [
                device
                for device in devices.values()
                if isinstance(device, MySensorsIRSwitch)
                and device.entity_id in entity_ids
            ]
        else:
            _devices = [
                device
                for device in devices.values()
                if isinstance(device, MySensorsIRSwitch)
            ]

        kwargs = {ATTR_IR_CODE: ir_code}
        for device in _devices:
            await device.async_turn_on(**kwargs)

    hass.services.async_register(
        MYSENSORS_DOMAIN,
        SERVICE_SEND_IR_CODE,
        async_send_ir_code_service,
        schema=SEND_IR_CODE_SERVICE_SCHEMA,
    )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, DOMAIN),
            async_discover,
        ),
    )


class MySensorsSwitch(mysensors.device.MySensorsEntity, SwitchEntity):
    """Representation of the value of a MySensors Switch child node."""

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._values.get(self.value_type) == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_ON
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_OFF
            self.async_write_ha_state()


class MySensorsIRSwitch(MySensorsSwitch):
    """IR switch child class to MySensorsSwitch."""

    def __init__(self, *args: Any) -> None:
        """Set up instance attributes."""
        super().__init__(*args)
        self._ir_code: str | None = None

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        set_req = self.gateway.const.SetReq
        return self._values.get(set_req.V_LIGHT) == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the IR switch on."""
        set_req = self.gateway.const.SetReq
        if ATTR_IR_CODE in kwargs:
            self._ir_code = kwargs[ATTR_IR_CODE]
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, self._ir_code
        )
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[self.value_type] = self._ir_code
            self._values[set_req.V_LIGHT] = STATE_ON
            self.async_write_ha_state()
            # Turn off switch after switch was turned on
            await self.async_turn_off()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the IR switch off."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 0, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[set_req.V_LIGHT] = STATE_OFF
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        await super().async_update()
        self._ir_code = self._values.get(self.value_type)
