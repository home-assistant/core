"""Base class for Qbus entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import re
from typing import Generic, TypeVar, cast

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory
from qbusmqttapi.state import QbusMqttState

from homeassistant.components.mqtt import ReceiveMessage, client as mqtt
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import QbusControllerCoordinator

_REFID_REGEX = re.compile(r"^\d+\/(\d+(?:\/\d+)?)$")

StateT = TypeVar("StateT", bound=QbusMqttState)


def add_new_outputs(
    coordinator: QbusControllerCoordinator,
    added_outputs: list[QbusMqttOutput],
    filter_fn: Callable[[QbusMqttOutput], bool],
    entity_type: type[QbusEntity],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Call async_add_entities for new outputs."""

    added_ref_ids = {k.ref_id for k in added_outputs}

    new_outputs = [
        output
        for output in coordinator.data
        if filter_fn(output) and output.ref_id not in added_ref_ids
    ]

    if new_outputs:
        added_outputs.extend(new_outputs)
        async_add_entities([entity_type(coordinator, output) for output in new_outputs])


def format_ref_id(ref_id: str) -> str | None:
    """Format the Qbus ref_id."""
    matches: list[str] = re.findall(_REFID_REGEX, ref_id)

    if len(matches) > 0:
        if ref_id := matches[0]:
            return ref_id.replace("/", "-")

    return None


class QbusEntity(Entity, Generic[StateT], ABC):
    """Representation of a Qbus entity."""

    _state_cls: type[StateT] = cast(type[StateT], QbusMqttState)

    _attr_has_entity_name = True
    _attr_name: str | None = None
    _attr_should_poll = False

    def __init__(
        self, coordinator: QbusControllerCoordinator, mqtt_output: QbusMqttOutput
    ) -> None:
        """Initialize the Qbus entity."""

        self._coordinator = coordinator
        self._mqtt_output = mqtt_output

        self._topic_factory = QbusMqttTopicFactory()
        self._message_factory = QbusMqttMessageFactory()
        self._state_topic = self._topic_factory.get_output_state_topic(
            mqtt_output.device.id, mqtt_output.id
        )

        ref_id = format_ref_id(mqtt_output.ref_id)

        self._attr_unique_id = f"ctd_{mqtt_output.device.serial_number}_{ref_id}"

        # Create linked device
        self._attr_device_info = DeviceInfo(
            name=mqtt_output.name.title(),
            manufacturer=MANUFACTURER,
            identifiers={(DOMAIN, f"{mqtt_output.device.serial_number}_{ref_id}")},
            suggested_area=mqtt_output.location.title(),
            via_device=(DOMAIN, format_mac(mqtt_output.device.mac)),
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
