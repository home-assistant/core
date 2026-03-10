"""Support for Qbus scene."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttState, StateAction, StateType

from homeassistant.components.scene import BaseScene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_new_entities

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
        entities = create_new_entities(
            coordinator,
            added_outputs,
            lambda output: output.type == "scene",
            QbusScene,
        )
        async_add_entities(entities)

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusScene(QbusEntity, BaseScene):
    """Representation of a Qbus scene entity."""

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize scene entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        self._attr_name = mqtt_output.name.title()

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        state = QbusMqttState(
            id=self._mqtt_output.id, type=StateType.ACTION, action=StateAction.ACTIVE
        )
        await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttState) -> None:
        self._async_record_activation()
