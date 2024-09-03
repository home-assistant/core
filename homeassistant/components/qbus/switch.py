"""Support for Qbus switch."""

import json
from typing import Any

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttOutput

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import QbusDataUpdateCoordinator
from .entity import QbusEntity

# from .qbus import QbusHub
from .qbus_entry import QbusEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities."""

    hub: QbusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    hub.register_platform("onoff", QbusSwitch, add_entities)


class QbusSwitch(QbusEntity, SwitchEntity):
    """Representation of a Qbus switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        mqtt_device: QbusDiscovery,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> None:
        """Initialize switch entity."""

        super().__init__(mqtt_output, mqtt_device, qbus_entry)

        self._is_on = False

        self._payload_on = json.dumps(mqtt_output.stateMessage.stateOn)
        self._payload_off = json.dumps(mqtt_output.stateMessage.stateOff)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await mqtt.async_publish(self.hass, self._command_topic, self._payload_on)
        self._is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await mqtt.async_publish(self.hass, self._command_topic, self._payload_off)
        self._is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        unsubscribe = await mqtt.async_subscribe(
            self.hass, self._state_topic, self._state_received
        )
        self.async_on_remove(unsubscribe)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

    async def _state_received(self, msg: ReceiveMessage) -> None:
        if len(msg.payload) <= 0:
            return

        self._is_on = "true" in msg.payload
        self.async_schedule_update_ha_state()
