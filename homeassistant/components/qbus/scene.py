"""Support for Qbus scene."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttState, StateAction, StateType

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, add_new_outputs, create_main_device_identifier

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up scene entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "scene",
            QbusScene,
            async_add_entities,
        )

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusScene(QbusEntity, Scene):
    """Representation of a Qbus scene entity."""

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize scene entity."""

        super().__init__(mqtt_output)

        # Add to main controller device
        self._attr_device_info = DeviceInfo(
            identifiers={create_main_device_identifier(mqtt_output)}
        )
        self._attr_name = mqtt_output.name.title()

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        state = QbusMqttState(
            id=self._mqtt_output.id, type=StateType.ACTION, action=StateAction.ACTIVE
        )
        await self._async_publish_output_state(state)

    async def _state_received(self, msg: ReceiveMessage) -> None:
        # Nothing to do
        pass
