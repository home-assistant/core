"""Support for Qbus scene."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttState, StateAction, StateType

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import QbusConfigEntry, QbusControllerCoordinator
from .entity import QbusEntity, add_new_outputs

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

    def __init__(
        self, coordinator: QbusControllerCoordinator, mqtt_output: QbusMqttOutput
    ) -> None:
        """Initialize scene entity."""

        super().__init__(coordinator, mqtt_output)

        # Add to main controller device
        self._attr_device_info = coordinator.device_info
        self._attr_name = mqtt_output.name.title()

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        state = QbusMqttState(
            id=self._mqtt_output.id, type=StateType.ACTION, action=StateAction.ACTIVE
        )
        await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttState) -> None:
        # We want users to be able to act on a scene activated with physical buttons
        # of Qbus. This lets users add entities from other integrations to a Qbus
        # scene (e.g. Hue, Sonos, etc).
        #
        # To accomplish this, users can use the state of a scene as a trigger in
        # their automations.
        #
        # The only way to update the state of a scene entity, is by setting the
        # private `__last_activated` variable of the parent `Scene` class.
        #
        # pylint: disable-next=attribute-defined-outside-init
        self._Scene__last_activated = dt_util.utcnow().isoformat()
