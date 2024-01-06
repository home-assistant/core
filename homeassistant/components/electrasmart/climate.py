"""Support for the Electra climate."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from electrasmart.api import STATUS_SUCCESS, Attributes, ElectraAPI, ElectraApiError
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_DELAY,
    CONSECUTIVE_FAILURE_THRESHOLD,
    DOMAIN,
    PRESET_NONE,
    PRESET_SHABAT,
    SCAN_INTERVAL_SEC,
    UNAVAILABLE_THRESH_SEC,
)

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


SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SEC)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Electra AC devices."""
    api: ElectraAPI = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Discovered %i Electra devices", len(api.devices))
    async_add_entities(
        (ElectraClimateEntity(device, api) for device in api.devices), True
    )


class ElectraClimateEntity(ClimateEntity):
    """Define an Electra climate."""

    _attr_fan_modes = ELECTRA_FAN_MODES
    _attr_target_temperature_step = 1
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = ELECTRA_MODES
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: ElectraAirConditioner, api: ElectraAPI) -> None:
        """Initialize Electra climate entity."""
        self._api = api
        self._electra_ac_device = device
        self._attr_unique_id = device.mac
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
        )

        swing_modes: list = []
        if Feature.V_SWING in self._electra_ac_device.features:
            swing_modes.append(SWING_VERTICAL)
        if Feature.H_SWING in self._electra_ac_device.features:
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._electra_ac_device.mac)},
            name=device.name,
            model=self._electra_ac_device.model,
            manufacturer=self._electra_ac_device.manufactor,
        )

        # This attribute will be used to mark the time we communicated
        # a command to the API
        self._last_state_update = 0

        # count the consecutive update failures, used to print error log
        self._consecutive_failures = 0
        self._skip_update = True
        self._was_available = True

        _LOGGER.debug("Added %s Electra AC device", self._attr_name)

    @property
    def available(self) -> bool:
        """Return True if the AC is available."""
        return (
            not self._electra_ac_device.is_disconnected(UNAVAILABLE_THRESH_SEC)
            and super().available
        )

    async def async_update(self) -> None:
        """Update Electra device."""

        # if we communicated a change to the API in the last API_DELAY seconds,
        # then don't receive any updates as the API takes few seconds
        # until it start sending it last recent change
        if self._last_state_update and int(time.time()) < (
            self._last_state_update + API_DELAY
        ):
            _LOGGER.debug("Skipping state update, keeping old values")
            return

        self._last_state_update = 0

        try:
            # skip the first update only as we already got the devices with their current state
            if self._skip_update:
                self._skip_update = False
            else:
                await self._api.get_last_telemtry(self._electra_ac_device)

            if not self.available:
                # show the warning once upon state change
                if self._was_available:
                    _LOGGER.warning(
                        "Electra AC %s (%s) is not available, check its status in the Electra Smart mobile app",
                        self.name,
                        self._electra_ac_device.mac,
                    )
                    self._was_available = False
                return

            if not self._was_available:
                _LOGGER.info(
                    "%s (%s) is now available",
                    self._electra_ac_device.mac,
                    self.name,
                )
                self._was_available = True

            _LOGGER.debug(
                "%s (%s) state updated: %s",
                self._electra_ac_device.mac,
                self.name,
                self._electra_ac_device.__dict__,
            )
        except ElectraApiError as exp:
            self._consecutive_failures += 1
            _LOGGER.warning(
                "Failed to get %s state: %s (try #%i since last success), keeping old state",
                self.name,
                exp,
                self._consecutive_failures,
            )

            if self._consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
                raise HomeAssistantError(
                    f"Failed to get {self.name} state: {exp} for the {self._consecutive_failures} time",
                ) from ElectraApiError

        self._consecutive_failures = 0
        self._update_device_attrs()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set AC fan mode."""
        mode = FAN_HASS_TO_ELECTRA[fan_mode]
        self._electra_ac_device.set_fan_speed(mode)
        await self._async_operate_electra_ac()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode == HVACMode.OFF:
            self._electra_ac_device.turn_off()
        else:
            self._electra_ac_device.set_mode(HVAC_MODE_HASS_TO_ELECTRA[hvac_mode])
            self._electra_ac_device.turn_on()

        await self._async_operate_electra_ac()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError("No target temperature provided")

        self._electra_ac_device.set_temperature(int(temperature))
        await self._async_operate_electra_ac()

    def _update_device_attrs(self) -> None:
        self._attr_fan_mode = FAN_ELECTRA_TO_HASS[
            self._electra_ac_device.get_fan_speed()
        ]
        self._attr_current_temperature = (
            self._electra_ac_device.get_sensor_temperature()
        )
        self._attr_target_temperature = self._electra_ac_device.get_temperature()

        self._attr_hvac_mode = (
            HVACMode.OFF
            if not self._electra_ac_device.is_on()
            else HVAC_MODE_ELECTRA_TO_HASS[self._electra_ac_device.get_mode()]
        )

        if (
            self._electra_ac_device.is_horizontal_swing()
            and self._electra_ac_device.is_vertical_swing()
        ):
            self._attr_swing_mode = SWING_BOTH
        elif self._electra_ac_device.is_horizontal_swing():
            self._attr_swing_mode = SWING_HORIZONTAL
        elif self._electra_ac_device.is_vertical_swing():
            self._attr_swing_mode = SWING_VERTICAL
        else:
            self._attr_swing_mode = SWING_OFF

        self._attr_preset_mode = (
            PRESET_SHABAT if self._electra_ac_device.get_shabat_mode() else PRESET_NONE
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set AC swing mdde."""
        if swing_mode == SWING_BOTH:
            self._electra_ac_device.set_horizontal_swing(True)
            self._electra_ac_device.set_vertical_swing(True)

        elif swing_mode == SWING_VERTICAL:
            self._electra_ac_device.set_horizontal_swing(False)
            self._electra_ac_device.set_vertical_swing(True)

        elif swing_mode == SWING_HORIZONTAL:
            self._electra_ac_device.set_horizontal_swing(True)
            self._electra_ac_device.set_vertical_swing(False)
        else:
            self._electra_ac_device.set_horizontal_swing(False)
            self._electra_ac_device.set_vertical_swing(False)

        await self._async_operate_electra_ac()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        if preset_mode == PRESET_SHABAT:
            self._electra_ac_device.set_shabat_mode(True)
        else:
            self._electra_ac_device.set_shabat_mode(False)

        await self._async_operate_electra_ac()

    async def _async_operate_electra_ac(self) -> None:
        """Send HVAC parameters to API."""

        try:
            resp = await self._api.set_state(self._electra_ac_device)
        except ElectraApiError as exp:
            raise HomeAssistantError(
                f"Error communicating with Electra API: {exp}"
            ) from exp

        if not (
            resp[Attributes.STATUS] == STATUS_SUCCESS
            and resp[Attributes.DATA][Attributes.RES] == STATUS_SUCCESS
        ):
            self._async_write_ha_state()
            raise HomeAssistantError(f"Failed to update {self.name}, error: {resp}")

        self._update_device_attrs()
        self._last_state_update = int(time.time())
        self._async_write_ha_state()
