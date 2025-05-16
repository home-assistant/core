"""Support for Qbus thermostat."""

import logging
from typing import Any

from qbusmqttapi.const import KEY_PROPERTIES_REGIME, KEY_PROPERTIES_SET_TEMPERATURE
from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttThermoState, StateType

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.mqtt import client as mqtt
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import QbusConfigEntry, QbusControllerCoordinator
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0

STATE_REQUEST_DELAY = 2

_LOGGER = logging.getLogger(__name__)


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

    _state_cls = QbusMqttThermoState

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: QbusControllerCoordinator, mqtt_output: QbusMqttOutput
    ) -> None:
        """Initialize climate entity."""

        super().__init__(coordinator, mqtt_output)

        self._attr_hvac_action = HVACAction.IDLE
        self._attr_hvac_mode = HVACMode.HEAT

        set_temp: dict[str, Any] = mqtt_output.properties.get(
            KEY_PROPERTIES_SET_TEMPERATURE, {}
        )
        current_regime: dict[str, Any] = mqtt_output.properties.get(
            KEY_PROPERTIES_REGIME, {}
        )

        self._attr_min_temp: float = set_temp.get("min", 0)
        self._attr_max_temp: float = set_temp.get("max", 35)
        self._attr_target_temperature_step: float = set_temp.get("step", 0.5)
        self._attr_preset_modes: list[str] = current_regime.get("enumValues", [])
        self._attr_preset_mode: str = (
            self._attr_preset_modes[0] if len(self._attr_preset_modes) > 0 else ""
        )

        self._request_state_debouncer: Debouncer | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._request_state_debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=STATE_REQUEST_DELAY,
            immediate=False,
            function=self._async_request_state,
        )
        await super().async_added_to_hass()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

        if preset_mode not in self._attr_preset_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_preset",
                translation_placeholders={
                    "preset": preset_mode,
                    "options": ", ".join(self._attr_preset_modes),
                },
            )

        state = QbusMqttThermoState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_regime(preset_mode)

        await self._async_publish_output_state(state)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is not None and isinstance(temperature, float):
            state = QbusMqttThermoState(id=self._mqtt_output.id, type=StateType.STATE)
            state.write_set_temperature(temperature)

            await self._async_publish_output_state(state)

    async def _handle_state_received(self, state: QbusMqttThermoState) -> None:
        if preset_mode := state.read_regime():
            self._attr_preset_mode = preset_mode

        if current_temperature := state.read_current_temperature():
            self._attr_current_temperature = current_temperature

        if target_temperature := state.read_set_temperature():
            self._attr_target_temperature = target_temperature

        self._set_hvac_action()

        # When the state type is "event", the payload only contains the changed
        # property. Request the state to get the full payload. However, changing
        # temperature step by step could cause a flood of state requests, so we're
        # holding off a few seconds before requesting the full state.
        if state.type == StateType.EVENT:
            assert self._request_state_debouncer is not None
            await self._request_state_debouncer.async_call()

    def _set_hvac_action(self) -> None:
        if self.target_temperature is None or self.current_temperature is None:
            self._attr_hvac_action = HVACAction.IDLE
            return

        self._attr_hvac_action = (
            HVACAction.HEATING
            if self.target_temperature > self.current_temperature
            else HVACAction.IDLE
        )

    async def _async_request_state(self) -> None:
        request = self._message_factory.create_state_request([self._mqtt_output.id])
        await mqtt.async_publish(self.hass, request.topic, request.payload)
