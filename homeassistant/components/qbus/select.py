"""Support for Qbus select."""

from qbusmqttapi.const import KEY_PROPERTIES_VALUE
from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttStepperState, StateType

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_new_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        """Add newly discovered outputs as entities."""
        entities = create_new_entities(
            coordinator,
            added_outputs,
            lambda output: output.type == "stepper",
            QbusStepper,
        )

        async_add_entities(entities)

    _check_outputs()
    coordinator.async_add_listener(_check_outputs)


class QbusStepper(QbusEntity, SelectEntity):
    """Representation of a Qbus stepper entity."""

    _state_cls = QbusMqttStepperState

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize stepper entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        self._attr_name = mqtt_output.name.title()

        value_settings: dict = mqtt_output.properties.get(KEY_PROPERTIES_VALUE, {})
        value_list: list[dict] = value_settings.get("valueList", [])

        self._name_to_value: dict[str, int] = {
            item["name"]: item["value"] for item in value_list
        }
        self._value_to_name: dict[int, str] = {
            item["value"]: item["name"] for item in value_list
        }
        self._attr_options = [item["name"] for item in value_list]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        value = self._name_to_value.get(option)

        if value is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "option": option,
                    "options": ", ".join(self._attr_options),
                },
            )

        state = QbusMqttStepperState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_value(value)

        await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttStepperState) -> None:
        """Update the state from a received Qbus state."""
        value = state.read_value()

        if value is not None:
            self._attr_current_option = self._value_to_name.get(value)
