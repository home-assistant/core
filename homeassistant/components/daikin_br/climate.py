"""Entity feature for the Daikin smart AC."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyiotdevice import (
    CommunicationErrorException,
    InvalidDataException,
    async_send_operation_data,
)

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_API_KEY, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry
from .entity import DaikinEntity

_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-instance-attributes, too-many-public-methods
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin Climate device from a config entry."""
    climate_entity = DaikinClimate(entry)

    # Add the entity
    async_add_entities([climate_entity])

    # Refresh after setup
    await climate_entity.coordinator.async_request_refresh()


# class DaikinClimate(ClimateEntity):
class DaikinClimate(DaikinEntity, ClimateEntity):
    """Representation of an Daikin Climate device."""

    _attr_name = None

    def __init__(self, config_entry: DaikinConfigEntry) -> None:
        """Initialize the climate device."""
        # Use the coordinator from runtime_data.
        self.coordinator = config_entry.runtime_data
        super().__init__(self.coordinator)
        self._attr_available = True

        # Extract device data from the config entry.
        device_data = config_entry.data

        self._device_key = device_data.get(CONF_API_KEY, None)

        _LOGGER.debug(
            "Initializing DaikinClimate - Name: %s, APN: %s",
            device_data.get("device_name"),
            device_data.get("device_apn"),
        )

        self._device_name = device_data.get("device_name", "Unknown")
        self._host = device_data.get("host", None)
        self._ip_address = self._host
        self._poll_interval = device_data.get("poll_interval")  # For future use
        self._command_suffix = device_data.get("command_suffix")

        # self._device_info = device_data
        self._device_info = dict(device_data)
        # self._unique_id = device_data.get("device_apn")
        self._unique_id = str(device_data.get("device_apn", ""))

        self._power_state = 0  # default is Off
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._hvac_mode = HVACMode.OFF
        self._power_state = 0  # default is Off
        self._target_temperature = None
        self._current_temperature = None
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.PRESET_MODE
        )

        # Define fan modes here, this could depend on the device's capabilities
        self._fan_modes = [
            "auto",
            "high",
            "medium_high",
            "medium",
            "low_medium",
            "low",
            "quiet",
        ]
        self._fan_mode = "auto"  # Default fan mode
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
        self._attr_preset_mode = PRESET_NONE
        self._attr_swing_modes = [SWING_OFF, SWING_VERTICAL]
        self._attr_swing_mode = SWING_OFF
        # Flag to skip updates
        self._skip_update = False

    @property
    def translation_key(self):
        """Return translation key climate entity."""
        return "daikin_ac"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the climate entity."""
        return self._unique_id

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        # Let the device registry supply the name, so return None here.
        return None

    @property
    def power_state(self):
        """Return the power state."""
        return self._power_state

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of supported HVAC modes."""
        return [
            HVACMode.OFF,
            HVACMode.FAN_ONLY,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.AUTO,
        ]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return self._attr_supported_features

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._attr_temperature_unit

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self._fan_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes."""
        return self._attr_preset_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._attr_preset_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of supported swing modes."""
        return self._attr_swing_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._attr_swing_mode

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 10.0  # Set to the device's minimum temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 32.0  # Set to the device's maximum temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step size for target temperature."""
        return 1.0  # Set the step size to 1 degree

    def map_hvac_mode(self, hvac_value):
        """Map device HVAC mode value to Home Assistant HVAC modes."""
        hvac_mapping = {
            0: HVACMode.OFF,
            6: HVACMode.FAN_ONLY,
            3: HVACMode.COOL,
            2: HVACMode.DRY,
            4: HVACMode.HEAT,
            1: HVACMode.AUTO,
        }
        return hvac_mapping.get(
            hvac_value, HVACMode.OFF
        )  # Default to HVAC_MODE_OFF if value is unknown

    def map_fan_speed(self, fan_value):
        """Map device fan speed value to Home Assistant fan modes."""
        fan_mapping = {
            17: "auto",
            7: "high",
            6: "medium_high",
            5: "medium",
            4: "low_medium",
            3: "low",
            18: "quiet",
        }
        return fan_mapping.get(
            fan_value, "auto"
        )  # Default to "auto" if value is unknown

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode on the AC device."""
        # Map Home Assistant HVAC modes to device modes
        hvac_mode_mapping = {
            HVACMode.OFF: 0,
            HVACMode.FAN_ONLY: 6,
            HVACMode.COOL: 3,
            HVACMode.DRY: 2,
            HVACMode.HEAT: 4,
            HVACMode.AUTO: 1,
        }

        # Get the corresponding mode value
        mode_value = hvac_mode_mapping.get(hvac_mode)

        if mode_value is None:
            _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
            return

        if mode_value == 0:
            data = {"port1": {"power": 0}}
        else:
            # Prepare the payload for the device
            data = {"port1": {"mode": mode_value, "power": 1}}

        # Serialize the payload to JSON
        json_data = json.dumps(data)

        # Use the common function to send the data and update state
        await self.set_thing_state(json_data)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode on the AC device."""
        # Map Home Assistant fan modes to device fan modes
        fan_mode_mapping = {
            "auto": 17,
            "high": 7,
            "medium_high": 6,
            "medium": 5,
            "low_medium": 4,
            "low": 3,
            "quiet": 18,
        }

        # Fan speed cannot be changed in DRY MODE
        if self._hvac_mode == HVACMode.DRY:
            message = (
                f"Fan mode change operation is not permitted in {self._hvac_mode} mode."
            )
            _LOGGER.error("Entity %s: %s", self.entity_id, message)
            self.async_write_ha_state()
            return

        # Get the corresponding fan mode value
        fan_mode_value = fan_mode_mapping.get(fan_mode)

        if fan_mode_value is None:
            _LOGGER.error("Unsupported fan mode")
            return

        # Prepare the payload for the device
        data = {"port1": {"fan": fan_mode_value}}

        # Serialize the payload to JSON
        json_data = json.dumps(data)

        # Use the common function to send the data and update state
        await self.set_thing_state(json_data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature on the AC device."""
        # Get the temperature value from kwargs
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            message = "Temperature not provided in the request."
            _LOGGER.error("Entity %s: %s", self.entity_id, message)
            return

        # Check HVAC mode and apply temperature range or restrictions
        if self._hvac_mode == HVACMode.COOL:
            if temperature < 16 or temperature > 32:
                message = f"Temperature {temperature}°C is out of range for COOL mode (16-32°C)."
                _LOGGER.error("Entity %s: %s", self.entity_id, message)
                # Revert the temperature dial to the previous value
                self._target_temperature = temperature
                self.async_write_ha_state()
                return
        elif self._hvac_mode in [HVACMode.FAN_ONLY, HVACMode.DRY]:
            message = f"Temperature cannot be changed in {self._hvac_mode} mode."
            _LOGGER.error("Entity %s: %s", self.entity_id, message)
            # Revert the temperature dial to the previous value
            self._target_temperature = temperature
            self.async_write_ha_state()
            return

        # Prepare the payload for the device
        data = {"port1": {"temperature": temperature}}

        # Serialize the payload to JSON
        json_data = json.dumps(data)

        # Use the common function to send the data and update state
        await self.set_thing_state(json_data)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode only if device is on (power_state = 1)."""
        data = None
        if self._power_state == 1:  # Check if the device is ON
            if preset_mode == PRESET_ECO:
                # Prepare the payload for the device
                data = {"port1": {"powerchill": 0, "econo": 1}}
                self._attr_preset_mode = PRESET_ECO
                self.schedule_update_ha_state()
            elif preset_mode == PRESET_BOOST:
                # Prepare the payload for the device
                data = {"port1": {"powerchill": 1, "econo": 0}}
                self._attr_preset_mode = PRESET_BOOST
                self.schedule_update_ha_state()
            elif preset_mode == PRESET_NONE:
                # Prepare the payload for the device
                data = {"port1": {"powerchill": 0, "econo": 0}}
                self._attr_preset_mode = PRESET_NONE
                self.schedule_update_ha_state()
        else:
            # Send a persistent notification when the device is off
            message = (
                "The device operation cannot be performed because it is turned off."
            )
            _LOGGER.error("Entity %s: %s", self.entity_id, message)
            self.async_write_ha_state()
            return

        if data is None:
            _LOGGER.error(
                "Entity %s: Unsupported preset mode: %s", self.entity_id, preset_mode
            )
            return

        # Serialize the payload to JSON
        json_data = json.dumps(data)

        # Use the common function to send the data and update state
        await self.set_thing_state(json_data)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode on the device."""
        # if swing_mode not in self._attr_swing_modes:
        if swing_mode not in (self._attr_swing_modes or []):
            _LOGGER.error("Unsupported swing mode: %s", swing_mode)
            return

        v_swing_value = None

        # Map the swing mode to the device-specific value
        if swing_mode == SWING_VERTICAL:  # "vertical":
            v_swing_value = 1
        elif swing_mode == SWING_OFF:  # "none":
            v_swing_value = 0

        # Prepare the payload
        data = {"port1": {"v_swing": v_swing_value}}

        # Serialize the payload to JSON
        json_data = json.dumps(data)

        # Send the updated swing mode to the device
        await self.set_thing_state(json_data)

    async def set_thing_state(self, data):
        """Send data and update internal state based on the response."""
        try:
            _LOGGER.debug("send command request: %s", data)
            # Send command using send_operation_data and await the response
            response = await async_send_operation_data(
                self._ip_address,
                self._device_key,
                data,
                self._command_suffix,
            )
            _LOGGER.debug("send command response: %s", response)

            # Update internal state based on the response
            port_status = response.get("port1", {})
            self._power_state = port_status.get("power")
            mode_value = port_status.get("mode")
            self._hvac_mode = (
                self.map_hvac_mode(mode_value) if self._power_state else HVACMode.OFF
            )
            self._target_temperature = port_status.get("temperature")
            self._current_temperature = port_status.get("sensors", {}).get("room_temp")
            self._fan_mode = self.map_fan_speed(port_status.get("fan"))
            # Update vertical swing state
            v_swing_value = port_status.get("v_swing", 0)  # Default to 0 if not present
            self._attr_swing_mode = SWING_VERTICAL if v_swing_value == 1 else SWING_OFF

            # Update the presets state
            v_econo_value = port_status.get("econo", 0)
            v_powerchill_value = port_status.get("powerchill", 0)
            if v_econo_value == 1:
                self._attr_preset_mode = PRESET_ECO

            if v_powerchill_value == 1:
                self._attr_preset_mode = PRESET_BOOST

            if v_econo_value == 0 and v_powerchill_value == 0:
                self._attr_preset_mode = PRESET_NONE

            _LOGGER.debug("Preset mode set to : %s", self._attr_preset_mode)

            # Update other properties if needed
            self.async_write_ha_state()

            # Skip update as we already know the new state
            self._skip_update = True

        except (InvalidDataException, CommunicationErrorException) as e:
            _LOGGER.error("Error executing command %s: %s", self._unique_id, e)

        # pylint: disable=broad-exception-caught
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to send command: %s", e)

    def update_entity_properties(self, status):
        """Asynchronously update entity properties based on the received status."""
        port_status = status.get("port1", {})

        self._current_temperature = port_status.get("sensors", {}).get("room_temp")
        self._target_temperature = port_status.get("temperature")

        # Map power state to HVAC mode
        self._power_state = port_status.get("power", 0)  # 0 = OFF, 1 = ON
        if self._power_state == 0:
            self._hvac_mode = HVACMode.OFF
        else:
            mode_value = port_status.get("mode", 0)  # Default to 0 if not present
            self._hvac_mode = self.map_hvac_mode(mode_value)

        # Update fan mode
        self._fan_mode = self.map_fan_speed(port_status.get("fan"))

        # Update vertical swing state
        v_swing_value = port_status.get("v_swing", 0)  # Default to 0 if not present
        self._attr_swing_mode = SWING_VERTICAL if v_swing_value == 1 else SWING_OFF

        # Update preset mode based on economy and power chill settings
        v_econo_value = port_status.get("econo", 0)
        v_powerchill_value = port_status.get("powerchill", 0)

        if v_econo_value == 1:
            self._attr_preset_mode = PRESET_ECO
        elif v_powerchill_value == 1:
            self._attr_preset_mode = PRESET_BOOST
        else:
            self._attr_preset_mode = PRESET_NONE

        # Write updated state asynchronously
        self.async_write_ha_state()

        # Skip this update cycle
        self._skip_update = True

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        try:
            if data and data.get("port1"):
                _LOGGER.debug(
                    "Updating entity properties - Name: %s, APN: %s",
                    self._device_name,
                    self._unique_id,
                )
                self.update_entity_properties(self.coordinator.data)
                self._attr_available = True
            else:
                self._attr_available = False
        # pylint: disable=broad-exception-caught
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error updating entity properties for %s: %s", self._unique_id, err
            )
            self._attr_available = False
        self.async_write_ha_state()
