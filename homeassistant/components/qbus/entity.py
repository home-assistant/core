"""Base class for Qbus entities."""

import re

from qbusmqttapi.discovery import QbusMqttDevice, QbusMqttOutput

from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .qbus_entry import QbusEntry


class QbusEntity(Entity):
    """Representation of a Qbus entity."""

    _REFID_REGEX = r"^\d+\/(\d+(?:\/\d+)?)$"

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        mqtt_device: QbusMqttDevice,
        qbus_entry: QbusEntry,
        id_suffix: str = "",
    ) -> None:
        """Initialize the Qbus entity."""

        ref_id = QbusEntity.format_ref_id(mqtt_output.ref_id)

        id_suffix = id_suffix or ""
        self._attr_unique_id = f"ctd_{mqtt_device.serial_number}_{ref_id}{id_suffix}"

        self._attr_device_info = DeviceInfo(
            name=f"CTD {mqtt_device.serial_number}",
            manufacturer="Qbus",
            identifiers={(DOMAIN, format_mac(mqtt_device.mac))},
            serial_number=mqtt_device.serial_number,
            # sw_version=mqtt_device.firmware_version,
        )

        self._attr_extra_state_attributes = {
            "controller_id": mqtt_device.id,
            "output_id": mqtt_output.id,
            "ref_id": mqtt_output.ref_id,
        }

        self._mqtt_output = mqtt_output
        self._mqtt_device = mqtt_device
        self._qbus_entry = qbus_entry

        self._command_topic = mqtt_output.command_topic
        self._state_topic = mqtt_output.state_topic

    @property
    def name(self):
        """Return the name of the entity."""
        return self._mqtt_output.name

    @staticmethod
    def format_ref_id(ref_id: str) -> str | None:
        """Format the Qbus ref_id."""
        matches = re.findall(QbusEntity._REFID_REGEX, ref_id)

        if len(matches) > 0:
            ref_id = matches[0]

            if ref_id:
                return ref_id.replace("/", "-")

        return None
