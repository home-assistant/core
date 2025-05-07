"""Support for Qbus cover."""

from typing import Any

from qbusmqttapi.const import (
    KEY_PROPERTIES_SHUTTER_POSITION,
    KEY_PROPERTIES_SLAT_POSITION,
)
from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttShutterState, StateType

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.mqtt import ReceiveMessage
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
    """Set up cover entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "shutter",
            QbusCover,
            async_add_entities,
        )

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusCover(QbusEntity, CoverEntity):
    """Representation of a Qbus cover entity."""

    _attr_supported_features: CoverEntityFeature
    _attr_device_class = CoverDeviceClass.BLIND

    def __init__(
        self, coordinator: QbusControllerCoordinator, mqtt_output: QbusMqttOutput
    ) -> None:
        """Initialize cover entity."""

        super().__init__(coordinator, mqtt_output)

        self._attr_assumed_state = False
        self._attr_current_cover_position = 0
        self._attr_current_cover_tilt_position = 0
        self._attr_is_closed = True

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        if "shutterStop" in mqtt_output.actions:
            self._attr_supported_features |= CoverEntityFeature.STOP
            self._attr_assumed_state = True

        if KEY_PROPERTIES_SHUTTER_POSITION in mqtt_output.properties:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if KEY_PROPERTIES_SLAT_POSITION in mqtt_output.properties:
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
            self._attr_supported_features |= CoverEntityFeature.OPEN_TILT
            self._attr_supported_features |= CoverEntityFeature.CLOSE_TILT

        self._target_shutter_position: int | None = None
        self._target_slat_position: int | None = None
        self._target_state: str | None = None
        self._previous_state: str | None = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)

        if self._attr_supported_features & CoverEntityFeature.SET_POSITION:
            state.write_position(100)
        else:
            state.write_state("up")

        await self._async_publish_output_state(state)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)

        if self._attr_supported_features & CoverEntityFeature.SET_POSITION:
            state.write_position(0)

            if self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION:
                state.write_slat_position(0)
        else:
            state.write_state("down")

        await self._async_publish_output_state(state)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_state("stop")
        await self._async_publish_output_state(state)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_position(int(kwargs[ATTR_POSITION]))
        await self._async_publish_output_state(state)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(50)
        await self._async_publish_output_state(state)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(0)
        await self._async_publish_output_state(state)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(int(kwargs[ATTR_TILT_POSITION]))
        await self._async_publish_output_state(state)

    async def _state_received(self, msg: ReceiveMessage) -> None:
        output = self._message_factory.parse_output_state(
            QbusMqttShutterState, msg.payload
        )

        if output is None:
            return

        state = output.read_state()
        shutter_position = output.read_position()
        slat_position = output.read_slat_position()

        if state is not None:
            self._previous_state = self._target_state
            self._target_state = state

        if shutter_position is not None:
            self._target_shutter_position = shutter_position

        if slat_position is not None:
            self._target_slat_position = slat_position

        self._update_is_closed()
        self._update_cover_position()
        self._update_tilt_position()
        self.async_schedule_update_ha_state()

    def _update_is_closed(self) -> None:
        if self._attr_supported_features & CoverEntityFeature.SET_POSITION:
            if self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION:
                self._attr_is_closed = (
                    self._target_shutter_position == 0
                    and self._target_slat_position in (0, 100)
                )
            else:
                self._attr_is_closed = self._target_shutter_position == 0
        else:
            self._attr_is_closed = (
                self._previous_state == "down" and self._target_state == "stop"
            )

    def _update_cover_position(self) -> None:
        self._attr_current_cover_position = (
            self._target_shutter_position
            if self._attr_supported_features & CoverEntityFeature.SET_POSITION
            else None
        )

    def _update_tilt_position(self) -> None:
        self._attr_current_cover_tilt_position = (
            self._target_slat_position
            if self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION
            else None
        )
