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

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: QbusConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities."""
    coordinator = entry.runtime_data

    # Keep a record of added entities
    known_items: list[QbusMqttOutput] = []

    # Local function that calls add_entities for new entities
    def _check_items() -> None:
        new_items = [
            item
            for item in coordinator.data
            if item.type == "onoff" and item.id not in {k.id for k in known_items}
        ]

        if new_items:
            known_items.extend(new_items)
            add_entities([QbusSwitch(item) for item in new_items])

    _check_items()
    entry.async_on_unload(coordinator.async_add_listener(_check_items))


class QbusSwitch(QbusEntity, SwitchEntity):
    """Representation of a Qbus switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
    ) -> None:
        """Initialize switch entity."""

        super().__init__(mqtt_output, ENTITY_ID_FORMAT)

        self._is_on = False

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
