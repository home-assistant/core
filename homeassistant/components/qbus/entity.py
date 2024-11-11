"""Base class for Qbus entities."""

import re

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory
from qbusmqttapi.state import QbusMqttState

from homeassistant.components.mqtt import ReceiveMessage, client as mqtt
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .qbus import QbusEntry

_REFID_REGEX = re.compile(r"^\d+\/(\d+(?:\/\d+)?)$")


def format_ref_id(ref_id: str) -> str | None:
    """Format the Qbus ref_id."""
    matches = re.findall(_REFID_REGEX, ref_id)

    if len(matches) > 0:
        if ref_id := matches[0]:
            return ref_id.replace("/", "-")

    return None


class QbusEntity(Entity):
    """Representation of a Qbus entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
        id_suffix: str = "",
    ) -> None:
        """Initialize the Qbus entity."""

        self._topic_factory = QbusMqttTopicFactory()
        self._message_factory = QbusMqttMessageFactory()

        ref_id = format_ref_id(mqtt_output.ref_id)

        id_suffix = id_suffix or ""
        self._attr_unique_id = (
            f"ctd_{mqtt_output.device.serial_number}_{ref_id}{id_suffix}"
        )

        self._attr_device_info = DeviceInfo(
            name=f"CTD {mqtt_output.device.serial_number}",
            manufacturer="Qbus",
            identifiers={(DOMAIN, format_mac(mqtt_output.device.mac))},
            serial_number=mqtt_output.device.serial_number,
            sw_version=mqtt_output.device.version,
        )

        self._attr_extra_state_attributes = {
            "controller_id": mqtt_output.device.id,
            "output_id": mqtt_output.id,
            "ref_id": mqtt_output.ref_id,
        }

        self._mqtt_output = mqtt_output
        self._qbus_entry = qbus_entry

        self._state_topic = self._topic_factory.get_output_state_topic(
            mqtt_output.device.id, mqtt_output.id
        )

    @property
    def name(self):
        """Return the name of the entity."""
        return self._mqtt_output.name

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        unsubscribe = await mqtt.async_subscribe(
            self.hass, self._state_topic, self._state_received
        )
        self.async_on_remove(unsubscribe)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

    async def _state_received(self, msg: ReceiveMessage) -> None:
        pass

    async def _async_publish_output_state(self, state: QbusMqttState) -> None:
        request = self._message_factory.create_set_output_state_request(
            self._mqtt_output.device, state
        )
        await mqtt.async_publish(self.hass, request.topic, request.payload)
