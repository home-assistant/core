"""Support for the Electra climate."""

import logging
from typing import Any, override

from electrasmart.api import STATUS_SUCCESS, Attributes, ElectraApiError
from electrasmart.device import ElectraAirConditioner, OperationMode
from electrasmart.device.const import MAX_TEMP, MIN_TEMP, Feature

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PRESET_NONE, PRESET_SHABAT, UNAVAILABLE_THRESH_SEC
from .coordinator import ElectraSmartConfigEntry, ElectraSmartCoordinator
from .entity import ElectraEntity

FAN_ELECTRA_TO_HASS = {
    OperationMode.FAN_SPEED_AUTO: FAN_AUTO,
    OperationMode.FAN_SPEED_LOW: FAN_LOW,
    OperationMode.FAN_SPEED_MED: FAN_MEDIUM,
    OperationMode.FAN_SPEED_HIGH: FAN_HIGH,
}

FAN_HASS_TO_ELECTRA = {
    FAN_AUTO: OperationMode.FAN_SPEED_AUTO,
    FAN_LOW: OperationMode.FAN_SPEED_LOW,
    FAN_MEDIUM: OperationMode.FAN_SPEED_MED,
    FAN_HIGH: OperationMode.FAN_SPEED_HIGH,
}

HVAC_MODE_ELECTRA_TO_HASS = {
    OperationMode.MODE_COOL: HVACMode.COOL,
    OperationMode.MODE_HEAT: HVACMode.HEAT,
    OperationMode.MODE_FAN: HVACMode.FAN_ONLY,
    OperationMode.MODE_DRY: HVACMode.DRY,
    OperationMode.MODE_AUTO: HVACMode.AUTO,
}

HVAC_MODE_HASS_TO_ELECTRA = {
    HVACMode.COOL: OperationMode.MODE_COOL,
    HVACMode.HEAT: OperationMode.MODE_HEAT,
    HVACMode.FAN_ONLY: OperationMode.MODE_FAN,
    HVACMode.DRY: OperationMode.MODE_DRY,
    HVACMode.AUTO: OperationMode.MODE_AUTO,
}

ELECTRA_FAN_MODES = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]
ELECTRA_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.AUTO,
]

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectraSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Electra AC devices."""
    coordinator = entry.runtime_data

    _LOGGER.debug("Discovered %i Electra devices", len(coordinator.api.devices))
    async_add_entities(
        ElectraClimateEntity(coordinator, device) for device in coordinator.api.devices
    )


class ElectraClimateEntity(ElectraEntity, ClimateEntity):
    """Define an Electra climate."""

    _attr_fan_modes = ELECTRA_FAN_MODES
    _attr_target_temperature_step = 1
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = ELECTRA_MODES
    _attr_name = None

    def __init__(
        self, coordinator: ElectraSmartCoordinator, device: ElectraAirConditioner
    ) -> None:
        """Initialize Electra climate entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = device.mac
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        swing_modes: list = []
        if Feature.V_SWING in device.features:
            swing_modes.append(SWING_VERTICAL)
        if Feature.H_SWING in device.features:
            swing_modes.append(SWING_HORIZONTAL)

        if all(elem in [SWING_HORIZONTAL, SWING_VERTICAL] for elem in swing_modes):
            swing_modes.append(SWING_BOTH)
        if swing_modes:
            swing_modes.append(SWING_OFF)
            self._attr_swing_modes = swing_modes
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        self._attr_preset_modes = [
            PRESET_NONE,
            PRESET_SHABAT,
        ]

        self._was_available = True

        _LOGGER.debug("Added %s Electra AC device", device.name)

    @property
    @override
    def available(self) -> bool:
        """Return True if the AC is available."""
        return (
            not self._device.is_disconnected(UNAVAILABLE_THRESH_SEC)
            and super().available
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Set the state from the telemetry fetched during setup."""
        await super().async_added_to_hass()
        self._update_device_attrs()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle a telemetry update from the coordinator."""
        if not self.available:
            # show the warning once upon state change
            if self._was_available:
                _LOGGER.warning(
                    "Electra AC %s (%s) is not available, check"
                    " its status in the Electra Smart mobile app",
                    self.entity_id,
                    self._device.mac,
                )
                self._was_available = False
        else:
            if not self._was_available:
                _LOGGER.debug(
                    "%s (%s) is now available",
                    self.entity_id,
                    self._device.mac,
                )
                self._was_available = True

            _LOGGER.debug(
                "%s (%s) state updated: %s",
                self.entity_id,
                self._device.mac,
                self._device.__dict__,
            )

        self._update_device_attrs()
        super()._handle_coordinator_update()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set AC fan mode."""
        mode = FAN_HASS_TO_ELECTRA[fan_mode]
        self._device.set_fan_speed(mode)
        await self._async_operate_electra_ac()

    @override
    async def async_turn_on(self) -> None:
        """Turn on, keeping the mode the AC was last running in."""
        if not self._device.turn_on():
            # The unit reports no previous mode to restore, so fall back to
            # cooling rather than leaving the AC off.
            self._device.set_mode(HVAC_MODE_HASS_TO_ELECTRA[HVACMode.COOL])

        await self._async_operate_electra_ac()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode == HVACMode.OFF:
            self._device.turn_off()
        else:
            self._device.set_mode(HVAC_MODE_HASS_TO_ELECTRA[hvac_mode])
            self._device.turn_on()

        await self._async_operate_electra_ac()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature.

        The climate service schema requires one of the temperature attributes
        and this entity only supports a target temperature, so the value is
        always there.
        """
        self._device.set_temperature(int(kwargs[ATTR_TEMPERATURE]))
        await self._async_operate_electra_ac()

    def _update_device_attrs(self) -> None:
        self._attr_fan_mode = FAN_ELECTRA_TO_HASS[self._device.get_fan_speed()]
        self._attr_native_current_temperature = self._device.get_sensor_temperature()
        self._attr_native_target_temperature = self._device.get_temperature()

        self._attr_hvac_mode = (
            HVACMode.OFF
            if not self._device.is_on()
            else HVAC_MODE_ELECTRA_TO_HASS[self._device.get_mode()]
        )

        if self._device.is_horizontal_swing() and self._device.is_vertical_swing():
            self._attr_swing_mode = SWING_BOTH
        elif self._device.is_horizontal_swing():
            self._attr_swing_mode = SWING_HORIZONTAL
        elif self._device.is_vertical_swing():
            self._attr_swing_mode = SWING_VERTICAL
        else:
            self._attr_swing_mode = SWING_OFF

        self._attr_preset_mode = (
            PRESET_SHABAT if self._device.get_shabat_mode() else PRESET_NONE
        )

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set AC swing mdde."""
        if swing_mode == SWING_BOTH:
            self._device.set_horizontal_swing(True)
            self._device.set_vertical_swing(True)

        elif swing_mode == SWING_VERTICAL:
            self._device.set_horizontal_swing(False)
            self._device.set_vertical_swing(True)

        elif swing_mode == SWING_HORIZONTAL:
            self._device.set_horizontal_swing(True)
            self._device.set_vertical_swing(False)
        else:
            self._device.set_horizontal_swing(False)
            self._device.set_vertical_swing(False)

        await self._async_operate_electra_ac()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        if preset_mode == PRESET_SHABAT:
            self._device.set_shabat_mode(True)
        else:
            self._device.set_shabat_mode(False)

        await self._async_operate_electra_ac()

    async def _async_operate_electra_ac(self) -> None:
        """Send HVAC parameters to API."""

        try:
            resp = await self.coordinator.api.set_state(self._device)
        except ElectraApiError as exp:
            raise HomeAssistantError(
                f"Error communicating with Electra API: {exp}"
            ) from exp

        if not (
            resp[Attributes.STATUS] == STATUS_SUCCESS
            and resp[Attributes.DATA][Attributes.RES] == STATUS_SUCCESS
        ):
            self._async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to update {self.entity_id}, error: {resp}"
            )

        # The API keeps serving the previous state for a few seconds, so the
        # polls of this device are skipped until it catches up.
        self.coordinator.async_command_sent(self._device.mac)
        self._update_device_attrs()
        self._async_write_ha_state()
