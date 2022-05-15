"""Support for the Electra climate."""
from __future__ import annotations

from datetime import timedelta
import logging
import time

import electra

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    PlatformNotReady,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API_DELAY, DOMAIN

FAN_ELECTRA_TO_HASS = {
    electra.OPER_FAN_SPEED_AUTO: FAN_AUTO,
    electra.OPER_FAN_SPEED_LOW: FAN_LOW,
    electra.OPER_FAN_SPEED_MED: FAN_MEDIUM,
    electra.OPER_FAN_SPEED_HIGH: FAN_HIGH,
}

FAN_HASS_TO_ELECTRA = {
    FAN_AUTO: electra.OPER_FAN_SPEED_AUTO,
    FAN_LOW: electra.OPER_FAN_SPEED_LOW,
    FAN_MEDIUM: electra.OPER_FAN_SPEED_MED,
    FAN_HIGH: electra.OPER_FAN_SPEED_HIGH,
}

HVAC_MODE_ELECTRA_TO_HASS = {
    electra.OPER_MODE_COOL: HVAC_MODE_COOL,
    electra.OPER_MODE_HEAT: HVAC_MODE_HEAT,
    electra.OPER_MODE_FAN: HVAC_MODE_FAN_ONLY,
    electra.OPER_MODE_DRY: HVAC_MODE_DRY,
    electra.OPER_MODE_AUTO: HVAC_MODE_AUTO,
}

HVAC_MODE_HASS_TO_ELECTRA = {
    HVAC_MODE_COOL: electra.OPER_MODE_COOL,
    HVAC_MODE_HEAT: electra.OPER_MODE_HEAT,
    HVAC_MODE_FAN_ONLY: electra.OPER_MODE_FAN,
    HVAC_MODE_DRY: electra.OPER_MODE_DRY,
    HVAC_MODE_AUTO: electra.OPER_MODE_AUTO,
}

HVAC_ACTION_ELECTRA_TO_HASS = {
    electra.OPER_MODE_COOL: CURRENT_HVAC_COOL,
    electra.OPER_MODE_HEAT: CURRENT_HVAC_HEAT,
    electra.OPER_MODE_FAN: CURRENT_HVAC_FAN,
    electra.OPER_MODE_DRY: CURRENT_HVAC_DRY,
}

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Electra AC devices."""
    api = hass.data[DOMAIN][entry.entry_id]

    devices = await get_devices(api)

    async_add_entities((ElectraClimate(device, api) for device in devices), True)


async def get_devices(api):
    """Return Electra."""
    _LOGGER.debug("Fetching Electra AC devices")
    try:
        return await api.get_devices()
    except electra.ElectraApiError as exp:
        err_message = f"Error communicating with API: {exp}"
        if "client error" in err_message:
            err_message += ", Check your internet connection."
            raise PlatformNotReady(err_message) from electra.ElectraApiError

        if electra.INTRUDER_LOCKOUT in err_message:
            err_message += ", You must re-authenticate by adding the integration again"
            raise ConfigEntryAuthFailed(err_message) from electra.ElectraApiError


class ElectraClimate(ClimateEntity):
    """Define an Electra sensor."""

    def __init__(self, device: electra.ElectraAirConditioner, api) -> None:
        """Initialize Electra climate entity."""
        self._api = api
        self._electra_ac_device = device
        self._attr_name = device.name
        self._attr_unique_id = device.mac
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.FAN_MODE
        )
        self._attr_fan_modes = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]
        self._attr_target_temperature_step = 1
        self._attr_max_temp = electra.MAX_TEMP
        self._attr_min_temp = electra.MIN_TEMP
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_swing_modes = [
            SWING_BOTH,
            SWING_HORIZONTAL,
            SWING_VERTICAL,
            SWING_OFF,
        ]
        self._attr_hvac_modes = [
            HVAC_MODE_OFF,
            HVAC_MODE_HEAT,
            HVAC_MODE_COOL,
            HVAC_MODE_DRY,
            HVAC_MODE_FAN_ONLY,
            HVAC_MODE_AUTO,
        ]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._electra_ac_device.mac)},
            name=self.name,
            model=self._electra_ac_device.model,
            manufacturer=self._electra_ac_device.manufactor,
        )

        # This attribute will be used to mark the time we communicated a command to the API
        self._last_state_update = 0

    async def async_update(self):
        """Update Electra device."""

        # if we communicated a change to the API in the last X seconds, don't receive any updates-
        # as the API takes few seconds until it start sending the last change
        if self._last_state_update and int(time.time()) < (
            self._last_state_update + API_DELAY
        ):
            _LOGGER.debug("Skipping state update, keeping old values")
            return

        self._last_state_update = 0

        try:
            await self._api.get_last_telemtry(self._electra_ac_device)
            _LOGGER.debug(
                "%s (%s) state updated: %s",
                self._electra_ac_device.mac,
                self._electra_ac_device.name,
                self._electra_ac_device.__dict__,
            )
        except electra.ElectraApiError as exp:
            _LOGGER.error(
                "Failed to get %s state: %s, keeping old state",
                self._electra_ac_device.name,
                exp,
            )
            raise HomeAssistantError from electra.ElectraApiError

        else:

            self._update_device_attrs()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set AC fand mode."""
        mode = FAN_HASS_TO_ELECTRA[fan_mode]
        self._electra_ac_device.set_fan_speed(mode)
        await self._async_update_electra_ac_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""

        if hvac_mode == HVAC_MODE_OFF:
            self._electra_ac_device.turn_off()
        else:
            self._electra_ac_device.set_mode(HVAC_MODE_HASS_TO_ELECTRA[hvac_mode])
            self._electra_ac_device.turn_on()

        await self._async_update_electra_ac_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        self._electra_ac_device.set_temperature(int(kwargs[ATTR_TEMPERATURE]))
        await self._async_update_electra_ac_state()

    def _update_device_attrs(self):

        self._attr_fan_mode = FAN_ELECTRA_TO_HASS[
            self._electra_ac_device.get_fan_speed()
        ]
        self._attr_current_temperature = (
            self._electra_ac_device.get_sensor_temperature()
        )
        self._attr_target_temperature = self._electra_ac_device.get_temperature()

        self._attr_hvac_mode = (
            HVAC_MODE_OFF
            if not self._electra_ac_device.is_on()
            else HVAC_MODE_ELECTRA_TO_HASS[self._electra_ac_device.get_mode()]
        )

        if self._electra_ac_device.get_mode() == electra.OPER_MODE_AUTO:
            self._attr_hvac_action = None
        else:
            self._attr_hvac_action = (
                CURRENT_HVAC_OFF
                if not self._electra_ac_device.is_on()
                else HVAC_ACTION_ELECTRA_TO_HASS[self._electra_ac_device.get_mode()]
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

        await self._async_update_electra_ac_state()

    async def _async_update_electra_ac_state(self) -> None:
        """Send HVAC parameters to API."""

        # No need to communicate with the API as the AC is off,
        # the change will be done once the AC is turned on
        if self._electra_ac_device.is_on() or (
            not self._electra_ac_device.is_on()
            and self._attr_hvac_mode != HVAC_MODE_OFF
        ):
            try:
                resp = await self._api.set_state(self._electra_ac_device)
            except electra.ElectraApiError as exp:
                err_message = f"Error communicating with API: {exp}"
                if "client error" in err_message:
                    err_message += ", Check your internet connection."
                    raise HomeAssistantError(err_message) from electra.ElectraApiError

                if electra.INTRUDER_LOCKOUT in err_message:
                    err_message += (
                        ", You must re-authenticate by adding the integration again"
                    )
                    raise ConfigEntryAuthFailed(
                        err_message
                    ) from electra.ElectraApiError
            else:
                if not (
                    resp[electra.ATTR_STATUS] == electra.STATUS_SUCCESS
                    and resp[electra.ATTR_DATA][electra.ATTR_RES]
                    == electra.STATUS_SUCCESS
                ):
                    raise HomeAssistantError(
                        f"Failed to update {self._attr_name}, error: {resp}"
                    )

                self._update_device_attrs()
                self._last_state_update = int(time.time())
                self._async_write_ha_state()
