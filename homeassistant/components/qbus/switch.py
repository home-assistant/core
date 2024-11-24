"""Support for Qbus switch."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttOnOffState, StateType

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity
from .qbus import QbusEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: QbusConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities."""
    entry.runtime_data.coordinator.register_platform("onoff", QbusSwitch, add_entities)


class QbusSwitch(QbusEntity, SwitchEntity):
    """Representation of a Qbus switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> None:
        """Initialize switch entity."""

        super().__init__(mqtt_output, qbus_entry, ENTITY_ID_FORMAT)

        self._is_on = False

    @classmethod
    def create(
        cls,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> "QbusSwitch":
        """Create an instance."""
        return QbusSwitch(mqtt_output, qbus_entry)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        state = QbusMqttOnOffState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_value(True)

        await self._async_publish_output_state(state)
        self._is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttOnOffState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_value(False)

        await self._async_publish_output_state(state)
        self._is_on = False

    async def _state_received(self, msg: ReceiveMessage) -> None:
        output = self._message_factory.parse_output_state(
            QbusMqttOnOffState, msg.payload
        )

        if output is not None:
            self._is_on = output.read_value()
            self.async_schedule_update_ha_state()
