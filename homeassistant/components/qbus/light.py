"""Support for Qbus light."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttAnalogState, StateType

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_new_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        entities = create_new_entities(
            coordinator,
            added_outputs,
            lambda output: output.type == "analog",
            QbusLight,
        )
        async_add_entities(entities)

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusLight(QbusEntity, LightEntity):
    """Representation of a Qbus light entity."""

    _state_cls = QbusMqttAnalogState

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize light entity."""

        super().__init__(mqtt_output)

        self._set_state(0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        state = QbusMqttAnalogState(id=self._mqtt_output.id)

        if brightness is None:
            state.type = StateType.ACTION
            state.write_on_off(on=True)
        else:
            percentage = round(brightness_to_value((1, 100), brightness))

            state.type = StateType.STATE
            state.write_percentage(percentage)

        await self._async_publish_output_state(state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.ACTION)
        state.write_on_off(on=False)

        await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttAnalogState) -> None:
        percentage = round(state.read_percentage())
        self._set_state(percentage)

    def _set_state(self, percentage: int) -> None:
        self._attr_is_on = percentage > 0
        self._attr_brightness = value_to_brightness((1, 100), percentage)
