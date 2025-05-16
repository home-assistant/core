"""Support for Qbus switch."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttOnOffState, StateType

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry, QbusControllerCoordinator
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "onoff",
            QbusSwitch,
            async_add_entities,
        )

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusSwitch(QbusEntity, SwitchEntity):
    """Representation of a Qbus switch entity."""

    _state_cls = QbusMqttOnOffState

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self, coordinator: QbusControllerCoordinator, mqtt_output: QbusMqttOutput
    ) -> None:
        """Initialize switch entity."""

        super().__init__(coordinator, mqtt_output)

        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        state = QbusMqttOnOffState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_value(True)

        await self._async_publish_output_state(state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttOnOffState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_value(False)

        await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttOnOffState) -> None:
        self._attr_is_on = state.read_value()
