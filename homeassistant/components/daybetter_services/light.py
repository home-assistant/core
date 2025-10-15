"""Support for DayBetter lights."""

from __future__ import annotations

import colorsys
import logging
from typing import Any
import uuid

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .daybetter_api import DayBetterApi
from .mqtt_manager import DayBetterMQTTManager

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the DayBetter Services component."""
    hass.data[DOMAIN] = {}
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DayBetter lights from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    devices = data["devices"]

    # Ensure devices is a list, even if it's None
    if devices is None:
        devices = []

    _LOGGER.debug("Original devices list: %s", devices)

    # Remove duplicate devices based on deviceId and deviceName
    unique_devices = []
    seen_devices = set()

    for dev in devices:
        # Create a unique key based on deviceId and deviceName
        device_id = dev.get("deviceId")
        device_name = dev.get("deviceName")
        unique_key = (device_id, device_name)

        _LOGGER.debug("Processing device: %s (ID: %s)", device_name, device_id)

        # Only add device if we haven't seen this combination before
        if unique_key not in seen_devices:
            seen_devices.add(unique_key)
            unique_devices.append(dev)
            _LOGGER.debug("Added device: %s (ID: %s)", device_name, device_id)
        else:
            _LOGGER.debug(
                "Skipping duplicate device: %s (ID: %s)", device_name, device_id
            )

    _LOGGER.debug("Unique devices list: %s", unique_devices)

    # Get light PIDs list
    pids_data = await api.fetch_pids()
    light_pids_str = pids_data.get("light", "")
    light_pids = set(light_pids_str.split(",")) if light_pids_str else set()

    _LOGGER.debug("Light PIDs string: %s", light_pids_str)
    _LOGGER.debug("Light PIDs set: %s", light_pids)

    # Check if each device's deviceMoldPid is in light_pids
    for dev in unique_devices:
        device_name = dev.get("deviceName", "unknown")
        device_mold_pid = dev.get("deviceMoldPid", "")
        is_light = device_mold_pid in light_pids
        _LOGGER.debug(
            "Device %s (PID: %s) is light: %s", device_name, device_mold_pid, is_light
        )

    lights = [
        DayBetterLight(hass, api, dev, data.get("mqtt_manager"))
        for dev in unique_devices
        if dev.get("deviceMoldPid") in light_pids
    ]

    _LOGGER.info("Created %d light entities", len(lights))
    async_add_entities(lights)


class DayBetterLight(LightEntity):
    """Representation of a DayBetter light."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DayBetterApi,
        device: dict[str, Any],
        mqtt_manager: DayBetterMQTTManager | None,
    ) -> None:
        """Initialize the light."""
        self.hass = hass
        self._api = api
        self._device = device
        self._mqtt_manager = mqtt_manager
        self._attr_name = device.get("deviceGroupName", "DayBetter Light")
        # Add debug logging
        _LOGGER.debug("Initializing DayBetterLight with device data: %s", device)
        # Use device name and all device attributes to generate more reliable unique ID
        device_name = device.get("deviceName", "unknown")
        device_id = device.get("id", "")
        device_mac = device.get("mac", "")
        device_group_id = device.get("deviceGroupId", "")
        device_mold_pid = device.get("deviceMoldPid", "")

        # Combine multiple identifiers to ensure uniqueness
        identifiers = [
            device_name,
            device_id,
            device_mac,
            device_group_id,
            device_mold_pid,
        ]
        # Filter out empty values and join
        unique_part = "_".join([str(ident) for ident in identifiers if ident])

        # If all identifiers are empty, use device name and a random number
        if not unique_part:
            unique_part = f"{device_name}_{uuid.uuid4().hex[:8]}"

        self._attr_unique_id = f"daybetter_{unique_part}"
        self._is_on = device.get("deviceState", 0) == 1
        self._brightness = 255  # Default maximum brightness
        self._hs_color = (0.0, 0.0)  # The default is white (hue, saturation)
        self._color_temp = 300  # Default color temperature (mireds unit)

        device_features = device.get("deviceFeatures", [])

        supported_modes = set()

        # Determine supported color modes based on device capabilities
        if 4 in device_features:  # Supports color temperature
            supported_modes.add(ColorMode.COLOR_TEMP)
        if 3 in device_features:  # Supports color
            supported_modes.add(ColorMode.HS)
        if 2 in device_features:  # Supports brightness
            supported_modes.add(ColorMode.BRIGHTNESS)

        # If no specific features, default to brightness support
        if not supported_modes:
            supported_modes.add(ColorMode.BRIGHTNESS)

        self._attr_supported_color_modes = supported_modes

        # Set current color mode
        if ColorMode.HS in supported_modes:
            self._attr_color_mode = ColorMode.HS
        elif ColorMode.COLOR_TEMP in supported_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ColorMode.BRIGHTNESS in supported_modes:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

        if ColorMode.COLOR_TEMP in supported_modes:
            self._min_mireds = 150
            self._max_mireds = 500

        self._device_features = device_features
        self._device_name = device.get("deviceName", "unknown")

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Register for MQTT updates if MQTT manager exists
        if self._mqtt_manager:
            # Register device switch status callback
            message_handler = self._mqtt_manager.get_message_handler()
            message_handler.register_device_switch_callback(
                self._handle_switch_status_update, self._device_name
            )

            # Register device brightness callback
            message_handler.register_device_brightness_callback(
                self._handle_brightness_update, self._device_name
            )

            # Register device color callback
            message_handler.register_device_color_callback(
                self._handle_color_update, self._device_name
            )

            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"daybetter_device_update_{self._device_name}",
                    self._handle_mqtt_update,
                )
            )

    @callback
    def _handle_switch_status_update(
        self, device_name: str, is_on: bool, device_type: int, topic: str
    ) -> None:
        """Handle switch status updates from MQTT."""
        _LOGGER.info(
            "🔄 Light switch callback called: %s, current device: %s, status: %s",
            device_name,
            self._device_name,
            is_on,
        )
        if device_name == self._device_name:
            _LOGGER.info(
                "✅ Light device name matches, updating status: %s -> %s",
                self._is_on,
                is_on,
            )
            self._is_on = is_on
            _LOGGER.info("🔄 Light calling async_write_ha_state()")
            self.async_write_ha_state()
            _LOGGER.info("✅ Light async_write_ha_state() call completed")
        else:
            _LOGGER.debug(
                "Light device name doesn't match, skipping update: %s != %s",
                device_name,
                self._device_name,
            )

    @callback
    def _handle_brightness_update(
        self, device_name: str, brightness: float, device_type: int, topic: str
    ) -> None:
        """Handle brightness updates from MQTT."""
        _LOGGER.info(
            "🔄 Light brightness callback called: %s, current device: %s, brightness: %s%%",
            device_name,
            self._device_name,
            brightness,
        )
        if device_name == self._device_name:
            # Convert percentage brightness to Home Assistant's 0-255 range
            ha_brightness = int((brightness / 100.0) * 255)
            _LOGGER.info(
                "✅ Light device name matches, updating brightness: %s -> %s (HA: %s)",
                self._brightness,
                brightness,
                ha_brightness,
            )
            self._brightness = ha_brightness
            _LOGGER.info("🔄 Light calling async_write_ha_state()")
            self.async_write_ha_state()
            _LOGGER.info("✅ Light async_write_ha_state() call completed")
        else:
            _LOGGER.debug(
                "Light device name doesn't match, skipping brightness update: %s != %s",
                device_name,
                self._device_name,
            )

    @callback
    def _handle_color_update(
        self, device_name: str, rgb_color: str, device_type: int, topic: str
    ) -> None:
        """Handle color updates from MQTT."""
        _LOGGER.info(
            "🔄 Light color callback called: %s, current device: %s, color: %s",
            device_name,
            self._device_name,
            rgb_color,
        )
        if device_name == self._device_name:
            try:
                # Convert RGB color string to HS color
                # Remove # prefix
                rgb_hex = rgb_color.lstrip("#")
                # Convert to RGB values
                r = int(rgb_hex[0:2], 16) / 255.0
                g = int(rgb_hex[2:4], 16) / 255.0
                b = int(rgb_hex[4:6], 16) / 255.0

                # Convert to HS color
                h, s, _ = colorsys.rgb_to_hsv(r, g, b)

                # Convert to degrees (0-360)
                hue = h * 360
                # Saturation is already in 0-1 range
                saturation = s * 100  # Convert to 0-100 range

                _LOGGER.info(
                    "✅ Light device name matches, updating color: %s -> HS(%s, %s)",
                    rgb_color,
                    hue,
                    saturation,
                )
                self._hs_color = (hue, saturation)
                _LOGGER.info("🔄 Light calling async_write_ha_state()")
                self.async_write_ha_state()
                _LOGGER.info("✅ Light async_write_ha_state() call completed")
            except Exception as e:
                _LOGGER.error("Error processing color update: %s", str(e))
        else:
            _LOGGER.debug(
                "Light device name doesn't match, skipping color update: %s != %s",
                device_name,
                self._device_name,
            )

    @callback
    def _handle_mqtt_update(self, state: dict) -> None:
        """Handle MQTT state updates."""
        _LOGGER.debug("Received MQTT update for %s: %s", self._device_name, state)

        # Update internal state based on MQTT message
        if "deviceState" in state:
            self._is_on = state["deviceState"] == 1

        if "brightness" in state:
            self._brightness = int(
                state["brightness"] * 255 / 100
            )  # Convert from percentage

        # Update HA state
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if (
            ColorMode.BRIGHTNESS in self._attr_supported_color_modes
            or ColorMode.HS in self._attr_supported_color_modes
            or ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            return self._brightness
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value."""
        if ColorMode.HS in self._attr_supported_color_modes:
            return self._hs_color
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return self._color_temp
        return None

    @property
    def min_mireds(self) -> int:
        """Return the coldest color temp that this light supports."""
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return getattr(self, "_min_mireds", 153)
        return 153

    @property
    def max_mireds(self) -> int:
        """Return the warmest color temp that this light supports."""
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return getattr(self, "_max_mireds", 500)
        return 500

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.get("deviceId", "unknown"))},
            "name": self._attr_name,
            "manufacturer": "DayBetter",
            "model": self._device.get("deviceMoldPid", "Unknown"),
            "sw_version": self._device.get("swVersion", "Unknown"),
            "hw_version": self._device.get("hwVersion", "Unknown"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Get the brightness value set by the user
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        # Processing color
        hs_color = kwargs.get(ATTR_HS_COLOR)
        if hs_color is not None:
            self._hs_color = hs_color

        # Handle color temperature
        color_temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if color_temp is not None:
            # Convert Kelvin to mireds
            self._color_temp = int(1000000 / color_temp)

        # Control equipment
        result = await self._api.control_device(
            self._device["deviceName"], True, brightness, hs_color, color_temp
        )

        # Update status based on control results
        if result.get("code", 1):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Control equipment
        result = await self._api.control_device(
            self._device["deviceName"], False, None, None, None
        )

        # Update status based on control results
        if result.get("code", 1):
            self._is_on = False
            self.async_write_ha_state()
