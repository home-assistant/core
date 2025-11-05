"""Platform for Hisense AC climate integration."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    SWING_OFF,
    SWING_VERTICAL,
    SWING_BOTH,
    SWING_HORIZONTAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MIN_TEMP,
    MAX_TEMP,
    StatusKey,
    FAN_AUTO,
    FAN_ULTRA_LOW,
    SFAN_ULTRA_LOW,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_ULTRA_HIGH,
    SFAN_ULTRA_HIGH,
)
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .api import HisenseApiClient
from .models import DeviceInfo as HisenseDeviceInfo
from connectlife_cloud.devices import get_device_parser
from connectlife_cloud.mode_converter import (
    find_device_value_for_ha_fan_mode,
    find_device_value_for_ha_mode,
    get_ha_fan_mode_string,
    get_ha_mode_string,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense AC climate platform."""
    coordinator: HisenseACPluginDataUpdateCoordinator = config_entry.runtime_data

    try:
        # Trigger initial data update
        await coordinator.async_config_entry_first_refresh()

        # Get devices from coordinator
        devices = coordinator.data
        _LOGGER.debug("Coordinator data after refresh: %s", devices)

        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        entities = []
        for device_id, device in devices.items():
            _LOGGER.debug("Processing device: %s", device.to_dict())
            if isinstance(device, HisenseDeviceInfo) and device.is_supported():
                _LOGGER.info(
                    "Adding climate entity for device: %s (type: %s-%s)",
                    device.name,
                    device.type_code,
                    device.feature_code
                )
                entity = HisenseClimate(coordinator, device)
                entities.append(entity)
            else:
                _LOGGER.warning(
                    "Skipping unsupported device: %s-%s (%s)",
                    getattr(device, 'type_code', None),
                    getattr(device, 'feature_code', None),
                    getattr(device, 'name', None)
                )

        if not entities:
            _LOGGER.warning("No supported devices found")
            return

        _LOGGER.info("Adding %d climate entities", len(entities))
        async_add_entities(entities)

    except Exception as err:
        _LOGGER.error("Failed to set up climate platform: %s", err)
        raise

class HisenseClimate(CoordinatorEntity, ClimateEntity):
    """Hisense AC climate entity."""

    _attr_has_entity_name = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1
    _attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
            self,
            coordinator: HisenseACPluginDataUpdateCoordinator,
            device: HisenseDeviceInfo,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_id = device.puid
        self._attr_unique_id = f"{device.device_id}_climate"
        self._attr_name = device.name
        self.hasAuto = False
        self._last_command_time = 0
        self.wait_time = 3
        self._cached_target_temp = None
        self._cached_hvac_mode = HVACMode.OFF
        self._cached_fan_mode = None
        self._cached_swing_mode = SWING_OFF
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        if device.feature_code == '19901':
            self._attr_target_temperature_step = 0.5
        # Get device parser to determine available modes and options
        device_type = device.get_device_type()
        if device_type:
            try:
                self._parser = coordinator.api_client.parsers.get(device.device_id)
                self.static_data = coordinator.api_client.static_data.get(device.device_id)
                _LOGGER.debug("Using parser for device type %s-%s:%s", device_type.type_code, device_type.feature_code,
                              self._parser)
                # Save device_type's type_code and feature_code for later use
                self._current_type_code = device_type.type_code
                self._current_feature_code = device_type.feature_code
                # Set available modes based on device capabilities
                self._setup_hvac_modes()
                self._setup_fan_modes()
                self._setup_swing_modes()
            except Exception as err:
                _LOGGER.error("Failed to get device parser: %s", err)
                self._parser = None
        else:
            self._parser = None

        # Only OFF mode if parser not available (don't assume device supports all modes)
        if not hasattr(self, '_attr_hvac_modes'):
            self._attr_hvac_modes = [HVACMode.OFF]

        # Get target_temp attribute
        target_temp_attr = self._parser.attributes.get(StatusKey.TARGET_TEMP) if self._parser else None

        # Parse propertyValueList to get temperature range
        def parse_temperature_range(property_value_list):
            ranges = []
            for item in property_value_list.split(','):
                item = item.strip()
                if '~' in item:
                    lower, upper = map(int, item.split('~'))
                    ranges.append((lower, upper))
            return ranges

        # Get parsed temperature range
        if target_temp_attr and target_temp_attr.value_range:
            temperature_ranges = parse_temperature_range(target_temp_attr.value_range)
        else:
            _LOGGER.warning("Target temperature attribute or value range not found, using default range.")
            temperature_ranges = [(MIN_TEMP, MAX_TEMP)]

        # Get temp_type attribute
        temp_type_attr = device.status.get(StatusKey.T_TEMP_TYPE)


        # Select appropriate temperature range based on temp_type
        if temp_type_attr != "1":
            # Use first range (Celsius)
            if temperature_ranges:
                min_temp, max_temp = temperature_ranges[0]
            else:
                min_temp = MIN_TEMP
                max_temp = MAX_TEMP
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            # Use second range (Fahrenheit)
            if len(temperature_ranges) > 1:
                min_temp, max_temp = temperature_ranges[1]
            else:
                min_temp = MIN_TEMP
                max_temp = MAX_TEMP
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        # Set attributes
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        _LOGGER.debug("Setting temperature limits %s-%s:%s:%s", device_type.type_code, device_type.feature_code,
                      self._attr_min_temp,self._attr_max_temp)
        if not hasattr(self, '_attr_fan_modes'):
            self._attr_fan_modes = [FAN_AUTO, SFAN_ULTRA_LOW, FAN_LOW, FAN_MEDIUM, FAN_HIGH, SFAN_ULTRA_HIGH]

        if not hasattr(self, '_attr_swing_modes'):
            self._attr_swing_modes = [SWING_OFF, SWING_VERTICAL]

    def _setup_hvac_modes(self):
        """Set up available HVAC modes based on device capabilities."""
        if not self._parser:
            return

        # Always include OFF mode
        modes = [HVACMode.OFF]
        has_heat = '1'
        if self.static_data:
            has_heat = self.static_data.get("Mode_settings")
        
        # Get work mode attribute from parser
        work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
        if work_mode_attr and work_mode_attr.value_map:
            # Use library function to convert mode strings
            available_ha_modes = set()
            for key, value in work_mode_attr.value_map.items():
                ha_mode_str = get_ha_mode_string(work_mode_attr.value_map, key)
                if ha_mode_str:
                    try:
                        ha_mode = HVACMode(ha_mode_str)
                        # Special handling for heat mode - check static data
                        if ha_mode == HVACMode.HEAT and has_heat != '1':
                            continue
                        available_ha_modes.add(ha_mode)
                    except ValueError:
                        # Invalid mode string, skip
                        continue

            # Add modes in preferred order
            desired_order = [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO]
            for mode in desired_order:
                if mode in available_ha_modes:
                    modes.append(mode)
        
        self._attr_hvac_modes = modes

    def _setup_fan_modes(self):
        """Set up available fan modes based on device capabilities."""
        if not self._parser:
            return
        position6_damper_control = '9'
        if self.static_data:
            position6_damper_control = self.static_data.get("Wind_speed_gear_selection")
        fan_modes = []
        fan_speed_attr = self._parser.attributes.get(StatusKey.FAN_SPEED)
        if fan_speed_attr and fan_speed_attr.value_map:
            # Use library function to convert fan mode strings
            for key, value in fan_speed_attr.value_map.items():
                ha_fan_mode_str = get_ha_fan_mode_string(fan_speed_attr.value_map, key)
                if ha_fan_mode_str:
                    # Map HA fan mode strings to const values
                    if ha_fan_mode_str == "auto":
                        fan_modes.append(FAN_AUTO)
                        self.hasAuto = True
                    elif ha_fan_mode_str == "ultra_low":
                        fan_modes.append(SFAN_ULTRA_LOW)
                    elif ha_fan_mode_str == "low":
                        fan_modes.append(FAN_LOW)
                    elif ha_fan_mode_str == "medium":
                        fan_modes.append(FAN_MEDIUM)
                    elif ha_fan_mode_str == "high":
                        fan_modes.append(FAN_HIGH)
                    elif ha_fan_mode_str == "ultra_high":
                        fan_modes.append(SFAN_ULTRA_HIGH)
                    elif ha_fan_mode_str == "medium_low":
                        fan_modes.append(SFAN_ULTRA_LOW)
                    elif ha_fan_mode_str == "medium_high":
                        fan_modes.append(SFAN_ULTRA_HIGH)

        if fan_modes:
            # Filter modes based on position6_damper_control
            if position6_damper_control != '9':
                # When it's 9: has 056789, when it's 7: has 0579
                fan_modes = [
                    mode for mode in fan_modes
                    if mode not in (SFAN_ULTRA_LOW, SFAN_ULTRA_HIGH)
                ]
            self._attr_fan_modes = fan_modes

    def _setup_swing_modes(self):
        """Set up available swing modes based on device capabilities."""
        if not self._parser:
            return
        left_and_right = '1'
        upper_and_lower = '1'
        if self.static_data:
            left_and_right = self.static_data.get("Left_and_right_damper_control")
            upper_and_lower = self.static_data.get("Upper_and_lower_damper_control")
        swing_modes = [SWING_OFF]

        # Check for vertical swing support (t_up_down)
        vertical_swing_attr = self._parser.attributes.get(StatusKey.SWING)
        if vertical_swing_attr and vertical_swing_attr.value_map:
            if upper_and_lower == '1':
                swing_modes.append(SWING_VERTICAL)

        # Special handling: if device feature_code == '199', disable horizontal swing
        if self._current_feature_code == '199':
            self._attr_swing_modes = swing_modes
            _LOGGER.debug("Device %s only supports vertical swing (SWING_VERTICAL)", self._device_id)
            return

        # Otherwise continue checking horizontal swing
        horizontal_swing_attr = self._parser.attributes.get("t_left_right")
        if horizontal_swing_attr and horizontal_swing_attr.value_map:
            if SWING_VERTICAL in swing_modes:
                if left_and_right == '1':
                    swing_modes.append(SWING_HORIZONTAL)
                    # swing_modes.append(SWING_BOTH)
            else:
                if left_and_right == '1':
                    swing_modes.append(SWING_HORIZONTAL)

        self._attr_swing_modes = swing_modes
        _LOGGER.debug("Available swing modes: %s", swing_modes)

    @property
    def _device(self):
        """Get current device data from coordinator."""
        device = self.coordinator.get_device(self._device_id)
        if device:
            _LOGGER.debug("Retrieved device %s with status: %s", self._device_id, device.status)
        return device

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device is not None and self._device.is_online

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self._device:
            return None
        temp = self._device.get_status_value(StatusKey.TEMPERATURE)
        return float(temp) if temp else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if not self._device:
            return None
        temp = self._device.get_status_value(StatusKey.TARGET_TEMP)
        return float(temp) if temp else None

    @property
    def hvac_mode(self) -> HVACMode:
        if time.time() - self._last_command_time < self.wait_time:
            return self._cached_hvac_mode
        """Return hvac operation mode."""
        if not self._device:
            return HVACMode.OFF

        power = self._device.get_status_value(StatusKey.POWER)
        if not power or power == "0":
            return HVACMode.OFF

        mode = self._device.get_status_value(StatusKey.MODE)
        if not mode:
            return HVACMode.OFF  # Default to OFF if mode is not set
        
        _LOGGER.debug("Current device %s mode %s", self._current_feature_code, mode)
        
        # Try to map the mode using the device parser
        if hasattr(self, '_parser') and self._parser:
            work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
            if work_mode_attr and work_mode_attr.value_map:
                ha_mode_str = get_ha_mode_string(work_mode_attr.value_map, mode)
                if ha_mode_str:
                    try:
                        return HVACMode(ha_mode_str)
                    except ValueError:
                        _LOGGER.warning("Invalid mode string: %s", ha_mode_str)
        
        # Fallback: try direct conversion if mode is already a valid HA mode string
        try:
            return HVACMode(mode)
        except ValueError:
            _LOGGER.warning("Could not convert mode %s to HVACMode, defaulting to OFF", mode)
            return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        if time.time() - self._last_command_time < self.wait_time and self._cached_fan_mode is not None:
            return self._cached_fan_mode
        """Return the fan setting."""
        if not self._device:
            return None

        fan_mode = self._device.get_status_value(StatusKey.FAN_SPEED)
        if not fan_mode:
            return FAN_AUTO  # Default to auto

        # Try to map using device parser
        if hasattr(self, '_parser') and self._parser:
            fan_attr = self._parser.attributes.get(StatusKey.FAN_SPEED)
            if fan_attr and fan_attr.value_map:
                ha_fan_mode_str = get_ha_fan_mode_string(fan_attr.value_map, fan_mode)
                if ha_fan_mode_str:
                    # Map HA fan mode strings to const values
                    if ha_fan_mode_str == "auto":
                        return FAN_AUTO
                    elif ha_fan_mode_str == "ultra_low":
                        return SFAN_ULTRA_LOW
                    elif ha_fan_mode_str == "low":
                        return FAN_LOW
                    elif ha_fan_mode_str == "medium":
                        return FAN_MEDIUM
                    elif ha_fan_mode_str == "high":
                        return FAN_HIGH
                    elif ha_fan_mode_str == "ultra_high":
                        return SFAN_ULTRA_HIGH
                    elif ha_fan_mode_str == "medium_low":
                        return SFAN_ULTRA_LOW
                    elif ha_fan_mode_str == "medium_high":
                        return SFAN_ULTRA_HIGH

        # Fallback to the raw value
        return fan_mode

    @property
    def fan_modes(self):
        modes = list(self._attr_fan_modes)
        if self.hvac_mode == HVACMode.FAN_ONLY:
            if FAN_AUTO in modes:
                modes.remove(FAN_AUTO)
        else:
            if FAN_AUTO not in modes and self.hasAuto:
                modes.append(FAN_AUTO)
        return modes
    @property
    def swing_mode(self) -> str | None:
        if time.time() - self._last_command_time < self.wait_time and self._cached_swing_mode is not None:
            return self._cached_swing_mode
        """Return the swing setting."""
        if not self._device:
            return None
        _LOGGER.debug("Swing mode change %s with status: %s", self._current_feature_code, self._device.status)
        # Get vertical swing status
        vertical_swing = self._device.get_status_value(StatusKey.SWING)

        # Get horizontal swing status
        horizontal_swing = self._device.get_status_value("t_left_right")
        # Special handling: if it's a 199 device, force horizontal swing to None (not supported)
        if self._current_feature_code == '199':
            horizontal_swing = None
        # Determine swing mode based on vertical and horizontal settings
        if (not vertical_swing or vertical_swing == "0") and (not horizontal_swing or horizontal_swing == "0"):
            return SWING_OFF
        elif vertical_swing == "1" and (not horizontal_swing or horizontal_swing == "0"):
            return SWING_VERTICAL
        elif (not vertical_swing or vertical_swing == "0") and horizontal_swing == "1":
            return SWING_HORIZONTAL
        # elif vertical_swing == "1" and horizontal_swing == "1":
        #     return SWING_BOTH

        # Default to off if we can't determine the mode
        return SWING_OFF

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.FAN_MODE
                | ClimateEntityFeature.SWING_MODE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
        )

        # Type check: only type 009 devices support swing functionality
        if self._current_type_code != '009':
            features &= ~ClimateEntityFeature.SWING_MODE

        # If swing modes count <= 1 (only auto mode), hide swing setting
        if len(self._attr_swing_modes) <= 1:
            features &= ~ClimateEntityFeature.SWING_MODE
        # Decide whether to support target temperature setting based on current mode
        current_mode = self.hvac_mode
        if current_mode not in [HVACMode.COOL, HVACMode.HEAT]:
            features &= ~ClimateEntityFeature.TARGET_TEMPERATURE

        # Disable fan mode setting in dehumidification mode
        if current_mode == HVACMode.DRY:
            features &= ~ClimateEntityFeature.FAN_MODE

        return features

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        # Check if current mode allows temperature setting
        current_mode = self.hvac_mode
        if current_mode in [HVACMode.FAN_ONLY, HVACMode.DRY, HVACMode.AUTO]:
            _LOGGER.debug("Temperature setting is not allowed in current mode: %s", current_mode)
            return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Setting temperature: %s: %s", kwargs, temperature)
        if temperature is None:
            return

        try:
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.TARGET_TEMP: str(temperature)},
            )
        except Exception as err:
            _LOGGER.error("Failed to set temperature: %s", err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # Update cache and timestamp
        self._cached_hvac_mode = hvac_mode
        self._cached_fan_mode = self.fan_mode
        self._cached_swing_mode = self.swing_mode
        self._cached_target_temp = self.target_temperature
        self._last_command_time = time.time()
        self.async_write_ha_state()
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        try:
            # Make sure the device is on first
            power = self._device.get_status_value(StatusKey.POWER)
            if not power or power == "0":
                await self.async_turn_on()

            # Find the Hisense mode value for this HA mode
            hisense_mode = None

            # Convert HVACMode enum to string (e.g., HVACMode.COOL -> "cool")
            mode_str = str(hvac_mode).lower().replace("hvacmode.", "")

            # Try to map using device parser with library function
            if hasattr(self, '_parser') and self._parser:
                work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
                if work_mode_attr and work_mode_attr.value_map:
                    hisense_mode = find_device_value_for_ha_mode(
                        work_mode_attr.value_map, mode_str
                    )
            if hvac_mode != HVACMode.OFF:
                power = self._device.get_status_value(StatusKey.POWER)
                if power == "0":
                    await self.coordinator.async_control_device(
                        puid=self._device_id,
                        properties={
                            StatusKey.POWER: "1",  # Turn on
                            StatusKey.MODE: hisense_mode  # Sync set mode
                        }
                    )
                    return
            if hisense_mode:
                _LOGGER.debug("Setting HVAC mode to %s (Hisense value: %s)", hvac_mode, hisense_mode)
                await self.coordinator.async_control_device(
                    puid=self._device_id,
                    properties={StatusKey.MODE: hisense_mode},
                )
            else:
                _LOGGER.error("Could not find Hisense mode value for HA mode: %s", hvac_mode)
        except Exception as err:
            _LOGGER.error("Failed to set hvac mode: %s", err)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        # Update cache and timestamp
        self._cached_fan_mode = fan_mode
        self._cached_hvac_mode = self.hvac_mode
        self._cached_swing_mode = self.swing_mode
        self._cached_target_temp = self.target_temperature
        self._last_command_time = time.time()
        self.async_write_ha_state()
        
        try:
            # Map HA fan mode constant to standard string
            fan_mode_map = {
                FAN_AUTO: "auto",
                FAN_LOW: "low",
                FAN_MEDIUM: "medium",
                FAN_HIGH: "high",
                FAN_ULTRA_LOW: "ultra_low",
                SFAN_ULTRA_LOW: "ultra_low",
                FAN_ULTRA_HIGH: "ultra_high",
                SFAN_ULTRA_HIGH: "ultra_high",
            }
            ha_fan_mode_str = fan_mode_map.get(fan_mode, fan_mode.lower().replace("_", ""))

            # Find the Hisense fan mode value using library function
            hisense_fan_mode = None
            if hasattr(self, '_parser') and self._parser:
                fan_attr = self._parser.attributes.get(StatusKey.FAN_SPEED)
                if fan_attr and fan_attr.value_map:
                    hisense_fan_mode = find_device_value_for_ha_fan_mode(
                        fan_attr.value_map, ha_fan_mode_str
                    )

            # Fallback to the fan mode as is
            if not hisense_fan_mode:
                hisense_fan_mode = fan_mode

            _LOGGER.debug("Setting fan mode to %s (Hisense value: %s)", fan_mode, hisense_fan_mode)
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.FAN_SPEED: hisense_fan_mode},
            )
        except Exception as err:
            _LOGGER.error("Failed to set fan mode: %s", err)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        # Update cache and timestamp
        self._cached_swing_mode = swing_mode
        self._cached_hvac_mode = self.hvac_mode
        self._cached_fan_mode = self.fan_mode
        self._cached_target_temp = self.target_temperature
        self._last_command_time = time.time()
        self.async_write_ha_state()
        """Set new target swing operation."""
        try:
            properties = {}

            # Determine vertical and horizontal swing settings based on mode
            if swing_mode == SWING_OFF:
                properties[StatusKey.SWING] = "0"
                properties["t_left_right"] = "0"
            elif swing_mode == SWING_VERTICAL:
                properties[StatusKey.SWING] = "1"
                properties["t_left_right"] = "0"
            elif swing_mode == SWING_HORIZONTAL:
                properties[StatusKey.SWING] = "0"
                properties["t_left_right"] = "1"
            # elif swing_mode == SWING_BOTH:
            #     properties[StatusKey.SWING] = "1"
            #     properties["t_left_right"] = "1"

            # Check which properties are supported by the device
            if hasattr(self, '_parser') and self._parser:
                # Only include properties that are supported by the device
                supported_properties = {}

                if StatusKey.SWING in properties and self._parser.attributes.get(StatusKey.SWING):
                    supported_properties[StatusKey.SWING] = properties[StatusKey.SWING]

                if "t_left_right" in properties and self._parser.attributes.get("t_left_right"):
                    supported_properties["t_left_right"] = properties["t_left_right"]

                # Send the command if we have supported properties
                if supported_properties:
                    _LOGGER.debug("Setting swing mode to %s with properties: %s", swing_mode, supported_properties)
                    await self.coordinator.async_control_device(
                        puid=self._device_id,
                        properties=supported_properties,
                    )

        except Exception as err:
            _LOGGER.error("Failed to set swing mode: %s", err)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        try:
            _LOGGER.debug("Turning on device %s", self._device_id)
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.POWER: "1"},
            )
        except Exception as err:
            _LOGGER.error("Failed to turn on: %s", err)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        try:
            _LOGGER.debug("Turning off device %s", self._device_id)
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.POWER: "0"},
            )
        except Exception as err:
            _LOGGER.error("Failed to turn off: %s", err)
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device(self._device_id)
        if not device:
            _LOGGER.warning("Device %s not found during sensor update", self._device_id)
            return
        # Only handle coordinator update after timeout
        if time.time() - self._last_command_time >= self.wait_time:
            super()._handle_coordinator_update()

