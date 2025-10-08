"""Base class for Qbus entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import re
from typing import cast

from qbusmqttapi.discovery import QbusMqttDevice, QbusMqttOutput
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory
from qbusmqttapi.state import QbusMqttState

from homeassistant.components.mqtt import ReceiveMessage, client as mqtt
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .coordinator import QbusControllerCoordinator

_REFID_REGEX = re.compile(r"^\d+\/(\d+(?:\/\d+)?)$")


def create_new_entities(
    coordinator: QbusControllerCoordinator,
    added_outputs: list[QbusMqttOutput],
    filter_fn: Callable[[QbusMqttOutput], bool],
    entity_type: type[QbusEntity],
) -> list[QbusEntity]:
    """Create entities for new outputs."""

    new_outputs = determine_new_outputs(coordinator, added_outputs, filter_fn)
    return [entity_type(output) for output in new_outputs]


def determine_new_outputs(
    coordinator: QbusControllerCoordinator,
    added_outputs: list[QbusMqttOutput],
    filter_fn: Callable[[QbusMqttOutput], bool],
) -> list[QbusMqttOutput]:
    """Determine new outputs."""

    added_ref_ids = {k.ref_id for k in added_outputs}

    new_outputs = (
        [
            output
            for output in coordinator.data.outputs
            if filter_fn(output) and output.ref_id not in added_ref_ids
        ]
        if coordinator.data
        else []
    )

    if new_outputs:
        added_outputs.extend(new_outputs)

    return new_outputs


def format_ref_id(ref_id: str) -> str | None:
    """Format the Qbus ref_id."""
    if match := _REFID_REGEX.search(ref_id):
        return match.group(1).replace("/", "-")

    return None


def create_device_identifier(mqtt_device: QbusMqttDevice) -> tuple[str, str]:
    """Create the device identifier."""
    return (DOMAIN, format_mac(mqtt_device.mac))


def create_unique_id(serial_number: str, suffix: str) -> str:
    """Create the unique id."""
    return f"ctd_{serial_number}_{suffix}"


class QbusEntity[StateT: QbusMqttState](Entity, ABC):
    """Representation of a Qbus entity."""

    _state_cls: type[StateT] = cast(type[StateT], QbusMqttState)

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        *,
        id_suffix: str = "",
        link_to_main_device: bool = False,
    ) -> None:
        """Initialize the Qbus entity."""

        self._mqtt_output = mqtt_output

        self._topic_factory = QbusMqttTopicFactory()
        self._message_factory = QbusMqttMessageFactory()
        self._state_topic = self._topic_factory.get_output_state_topic(
            mqtt_output.device.id, mqtt_output.id
        )

        ref_id = format_ref_id(mqtt_output.ref_id)
        suffix = ref_id or ""

        if id_suffix:
            suffix += f"_{id_suffix}"

        self._attr_unique_id = create_unique_id(
            mqtt_output.device.serial_number, suffix
        )

        if link_to_main_device:
            self._attr_device_info = DeviceInfo(
                identifiers={create_device_identifier(mqtt_output.device)}
            )
        else:
            self._attr_device_info = DeviceInfo(
                name=mqtt_output.name.title(),
                manufacturer=MANUFACTURER,
                identifiers={(DOMAIN, f"{mqtt_output.device.serial_number}_{ref_id}")},
                suggested_area=mqtt_output.location.title(),
                via_device=create_device_identifier(mqtt_output.device),
            )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            await mqtt.async_subscribe(
                self.hass, self._state_topic, self._state_received
            )
        )

    async def _state_received(self, msg: ReceiveMessage) -> None:
        state = self._message_factory.parse_output_state(self._state_cls, msg.payload)

        if isinstance(state, self._state_cls):
            await self._handle_state_received(state)
            self.async_schedule_update_ha_state()

    @abstractmethod
    async def _handle_state_received(self, state: StateT) -> None:
        raise NotImplementedError

    async def _async_publish_output_state(self, state: QbusMqttState) -> None:
        request = self._message_factory.create_set_output_state_request(
            self._mqtt_output.device, state
        )
        await mqtt.async_publish(self.hass, request.topic, request.payload)
