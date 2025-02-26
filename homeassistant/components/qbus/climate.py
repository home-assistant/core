"""Support for Qbus thermostat."""

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.mqtt import ReceiveMessage, client as mqtt
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from qbusmqttapi.const import KEY_PROPERTIES_REGIME, KEY_PROPERTIES_SET_TEMPERATURE
from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttThermoState, StateType

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0

STATE_REQUEST_DELAY = timedelta(seconds=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "thermo",
            QbusClimate,
            async_add_entities,
        )

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusClimate(QbusEntity, ClimateEntity):
    """Representation of a Qbus climate entity."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize climate entity."""

        super().__init__(mqtt_output)

        self._attr_hvac_action = HVACAction.IDLE
        self._attr_hvac_mode = HVACMode.OFF

        set_temp: dict = mqtt_output.properties.get(KEY_PROPERTIES_SET_TEMPERATURE, {})
        current_regime: dict = mqtt_output.properties.get(KEY_PROPERTIES_REGIME, {})

        self._attr_min_temp = set_temp.get("min", 0)
        self._attr_max_temp = set_temp.get("max", 35)
        self._attr_target_temperature_step = set_temp.get("step", 0.5)
        self._attr_preset_modes = current_regime.get("enumValues", [])
        self._attr_preset_mode = (
            self._attr_preset_modes[0] if len(self._attr_preset_modes) > 0 else ""
        )

        self._cancel_state_request: CALLBACK_TYPE | None = None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        state = QbusMqttThermoState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_regime(preset_mode)

        await self._async_publish_output_state(state)
        self._attr_preset_mode = preset_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is not None and isinstance(temperature, float):
            state = QbusMqttThermoState(id=self._mqtt_output.id, type=StateType.STATE)
            state.write_set_temperature(temperature)

            await self._async_publish_output_state(state)
            self._attr_target_temperature = temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # It is not supported to explicitly set the HVAC mode. The value
        # is determined automatically.

    async def _state_received(self, msg: ReceiveMessage) -> None:
        state = self._message_factory.parse_output_state(
            QbusMqttThermoState, msg.payload
        )

        if state is None:
            return

        self._attr_preset_mode = state.read_regime() or self._attr_preset_mode
        self._attr_current_temperature = (
            state.read_current_temperature() or self._attr_current_temperature
        )
        self._attr_target_temperature = (
            state.read_set_temperature() or self._attr_target_temperature
        )

        self._determine_hvac_mode_and_action()

        # When the state type is "event", the payload only contains the changed
        # property. Request the state to get the full payload. However, changing
        # temperature step by step could cause a flood of state requests, so we're
        # holding off a few seconds before requesting the full state.
        if state.type == StateType.EVENT:
            if self._cancel_state_request is not None:
                self._cancel_state_request()
                self._cancel_state_request = None

            self._cancel_state_request = async_call_later(
                self.hass, STATE_REQUEST_DELAY, self._async_request_state
            )

        self.async_schedule_update_ha_state()

    def _determine_hvac_mode_and_action(self) -> None:
        if self.target_temperature is None or self.current_temperature is None:
            self._attr_hvac_action = HVACAction.IDLE
            self._attr_hvac_mode = HVACMode.OFF
            return

        self._attr_hvac_action = (
            HVACAction.HEATING
            if self.target_temperature > self.current_temperature
            else HVACAction.IDLE
        )
        self._attr_hvac_mode = (
            HVACMode.HEAT
            if self.target_temperature > self.current_temperature
            else HVACMode.OFF
        )

    async def _async_request_state(self, _: datetime) -> None:
        request = self._message_factory.create_state_request([self._mqtt_output.id])
        await mqtt.async_publish(self.hass, request.topic, request.payload)
