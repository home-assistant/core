"""Message Handler for DayBetter Services.

This module handles MQTT message processing and device status management
for DayBetter devices.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class DayBetterMessageHandler:
    """Handler class for processing DayBetter device MQTT messages"""

    def __init__(self, hass=None):
        """Initialize message handler

        Args:
            hass: Home Assistant instance for integration functions
        """
        self.hass = hass
        self._device_status_callbacks = {}
        self._message_callbacks = {}
        _LOGGER.debug("Created new DayBetterMessageHandler instance: %s", id(self))

    def process_mqtt_message(self, topic: str, payload: str) -> bool:
        """Process received MQTT message

        Args:
            topic: MQTT topic
            payload: Message content

        Returns:
            bool: Whether processing was successful
        """
        try:
            _LOGGER.info("📨 Received MQTT message:")
            _LOGGER.info("   Topic: %s", topic)
            _LOGGER.info("   Content: %s", payload)
            _LOGGER.info("   Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # Attempting to parse JSON message
            try:
                import json

                data = json.loads(payload)
                _LOGGER.info("   JSON parsing successful: %s", data)

                # Process device status information
                return self._process_device_status(data, topic)

            except json.JSONDecodeError as e:
                _LOGGER.debug("   JSON parsing failed: %s", str(e))
                return False

        except Exception as e:
            _LOGGER.error("Error processing MQTT message: %s", str(e))
            return False

    def _process_device_status(self, data: dict[str, Any], topic: str) -> bool:
        """Process device status information

        Args:
            data: Parsed JSON data
            topic: MQTT topic

        Returns:
            bool: Whether processing was successful
        """
        try:
            # Check if necessary fields exist
            if not isinstance(data, dict):
                _LOGGER.debug(
                    "Device status data is not in dictionary format, skipping processing"
                )
                return False

            # Extract device information
            device_name = data.get("deviceName")
            device_type = data.get("type")

            if not device_name:
                _LOGGER.debug("Missing deviceName field in device status message")
                return False

            if device_type is None:
                _LOGGER.debug("Missing type field in device status message")
                return False

            # Process different status fields based on device type
            if device_type == 0:
                # type=0: Process online field to determine device online status
                online_status = data.get("online")
                if online_status is None:
                    _LOGGER.debug("Device type is 0 but missing online field")
                    return False

                is_online = bool(online_status)
                status_text = "Online" if is_online else "Offline"

                _LOGGER.info("🔌 Device online status update:")
                _LOGGER.info("   Device ID: %s", device_name)
                _LOGGER.info("   Device Type: %s (Online Status)", device_type)
                _LOGGER.info("   Online Status: %s (%s)", status_text, online_status)
                _LOGGER.info("   Message Topic: %s", topic)
                _LOGGER.info(
                    "   Update Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                # Update device status in Home Assistant
                self._update_device_status_in_hass(device_name, is_online, device_type)

                # Trigger device status callback
                self._trigger_device_status_callbacks(
                    device_name, is_online, device_type, topic
                )

            elif device_type == 1:
                # type=1: Process on field to determine device switch status
                on_status = data.get("on")
                if on_status is None:
                    _LOGGER.debug("Device Type is 1 but missing on field")
                    return False

                is_on = bool(on_status)
                status_text = "On" if is_on else "Off"

                _LOGGER.info("🔌 Device switch status update:")
                _LOGGER.info("   Device ID: %s", device_name)
                _LOGGER.info("   Device Type: %s (Switch Status)", device_type)
                _LOGGER.info("   Switch Status: %s (%s)", status_text, on_status)
                _LOGGER.info("   Message Topic: %s", topic)
                _LOGGER.info(
                    "   Update Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                # Update device status in Home Assistant
                self._update_device_switch_status_in_hass(
                    device_name, is_on, device_type
                )

                # Trigger device status callback
                self._trigger_device_switch_callbacks(
                    device_name, is_on, device_type, topic
                )

            elif device_type == 2:
                # type=2: Process device brightness data
                brightness = data.get("brightness")

                if brightness is None:
                    _LOGGER.debug("Device Type is 2 but missing brightness field")
                    return False

                # Validate brightness value range (0~100)
                try:
                    brightness_value = float(brightness)
                    if brightness_value < 0 or brightness_value > 100:
                        _LOGGER.warning(
                            "Brightness value out of valid range (0~100): %s",
                            brightness_value,
                        )
                        brightness_value = max(
                            0, min(100, brightness_value)
                        )  # Limit to valid range
                        _LOGGER.info(
                            "Brightness value has been limited to valid range: %s",
                            brightness_value,
                        )
                except (ValueError, TypeError) as e:
                    _LOGGER.error("Brightness value format error: %s", str(e))
                    return False

                _LOGGER.info("💡 Device brightness data update:")
                _LOGGER.info("   Device ID: %s", device_name)
                _LOGGER.info("   Device Type: %s (Brightness Data)", device_type)
                _LOGGER.info("   Brightness Value: %s%%", brightness_value)
                _LOGGER.info("   Message Topic: %s", topic)
                _LOGGER.info(
                    "   Update Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                # Update device brightness status in Home Assistant
                self._update_device_brightness_in_hass(
                    device_name, brightness_value, device_type
                )

                # Trigger device brightness callback
                self._trigger_device_brightness_callbacks(
                    device_name, brightness_value, device_type, topic
                )

            elif device_type == 3:
                # type=3: Process light color data
                rgb = data.get("rgb")

                if rgb is None:
                    _LOGGER.debug("Device Type is 3 but missing rgb field")
                    return False

                # Validate RGB color value format
                try:
                    rgb_str = str(rgb).upper().strip()
                    # Remove possible # prefix
                    rgb_str = rgb_str.removeprefix("#")

                    # Validate if it is a 6-digit hexadecimal string
                    if len(rgb_str) != 6:
                        _LOGGER.error(
                            "RGB color value length is incorrect, should be 6 digits: %s",
                            rgb_str,
                        )
                        return False

                    # Validate if it is a valid hexadecimal string
                    int(rgb_str, 16)

                    # Format to standard format
                    rgb_formatted = f"#{rgb_str}"

                except ValueError as e:
                    _LOGGER.error(
                        "RGB color value format error, should be a 6-digit hexadecimal string: %s",
                        str(e),
                    )
                    return False

                _LOGGER.info("🎨 Device color data update:")
                _LOGGER.info("   Device ID: %s", device_name)
                _LOGGER.info("   Device Type: %s (Color Data)", device_type)
                _LOGGER.info("   Color Value: %s", rgb_formatted)
                _LOGGER.info("   Message Topic: %s", topic)
                _LOGGER.info(
                    "   Update Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                # Update device color status in Home Assistant
                self._update_device_color_in_hass(
                    device_name, rgb_formatted, device_type
                )

                # Trigger device color callback
                self._trigger_device_color_callbacks(
                    device_name, rgb_formatted, device_type, topic
                )

            elif device_type == 5:
                # type=5: Process temperature and humidity sensor data (temp and humi fields)
                temp_raw = data.get("temp")
                humi_raw = data.get("humi")

                if temp_raw is not None:
                    # temp field: Temperature (Celsius, with one decimal place, e.g., 294=29.4°C)
                    temp_value = float(temp_raw) / 10.0
                    _LOGGER.info("🌡️ Sensor temperature data update (type=5):")
                    _LOGGER.info("   Device ID: %s", device_name)
                    _LOGGER.info("   Device Type: %s (Sensor Data)", device_type)
                    _LOGGER.info("   Raw Temperature Value: %s", temp_raw)
                    _LOGGER.info("   Converted Temperature Value: %s°C", temp_value)
                    _LOGGER.info("   Message Topic: %s", topic)
                    _LOGGER.info(
                        "   Update Time: %s",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )

                    # Update sensor status in Home Assistant
                    self._update_sensor_data_in_hass(
                        device_name, "temperature", temp_value, device_type
                    )

                    # Trigger sensor data callback
                    self._trigger_sensor_data_callbacks(
                        device_name, "temperature", temp_value, device_type, topic
                    )

                if humi_raw is not None:
                    # humi field: Humidity (range 1~100, with one decimal place, e.g., 614=61.4%)
                    humi_value = float(humi_raw) / 10.0
                    _LOGGER.info("💧 Sensor humidity data update (type=5):")
                    _LOGGER.info("   Device ID: %s", device_name)
                    _LOGGER.info("   Device Type: %s (Sensor Data)", device_type)
                    _LOGGER.info("   Raw Humidity Value: %s", humi_raw)
                    _LOGGER.info("   Converted Humidity Value: %s%%", humi_value)
                    _LOGGER.info("   Message Topic: %s", topic)
                    _LOGGER.info(
                        "   Update Time: %s",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )

                    # Update sensor status in Home Assistant
                    self._update_sensor_data_in_hass(
                        device_name, "humidity", humi_value, device_type
                    )

                    # Trigger sensor data callback
                    self._trigger_sensor_data_callbacks(
                        device_name, "humidity", humi_value, device_type, topic
                    )

                if temp_raw is None and humi_raw is None:
                    _LOGGER.debug("Device Type is 5 but missing temp and humi fields")
                    return False

            else:
                _LOGGER.debug(
                    "Unknown Device Type: %s, skipping processing", device_type
                )
                return False

            return True

        except Exception as e:
            _LOGGER.error("Error processing device status: %s", str(e))
            return False

    def _update_device_status_in_hass(
        self, device_name: str, is_online: bool, device_type: int
    ):
        """Update device status in Home Assistant

        Args:
            device_name: Device unique ID
            is_online: Whether device is online
            device_type: Device Type
        """
        try:
            # Log status update
            _LOGGER.debug(
                "Preparing to update device status in Home Assistant: %s -> %s",
                device_name,
                "Online" if is_online else "Offline",
            )

            # Specific Home Assistant integration logic can be added here
            # For example：
            # - Update sensor status
            # - Trigger automation
            # - Send notifications, etc.

            if self.hass:
                # Trigger Home Assistant event
                event_data = {
                    "device_name": device_name,
                    "is_online": is_online,
                    "device_type": device_type,
                    "timestamp": datetime.now().isoformat(),
                }

                # Trigger custom event
                self.hass.bus.fire("daybetter_device_status_changed", event_data)
                _LOGGER.debug(
                    "Triggered Home Assistant event: daybetter_device_status_changed"
                )

        except Exception as e:
            _LOGGER.error("Error updating Home Assistant device status: %s", str(e))

    def _update_device_switch_status_in_hass(
        self, device_name: str, is_on: bool, device_type: int
    ):
        """Update device switch status in Home Assistant

        Args:
            device_name: Device unique ID
            is_on: Whether device is on
            device_type: Device Type
        """
        try:
            # Log status update
            _LOGGER.debug(
                "Preparing to update device switch status in Home Assistant: %s -> %s",
                device_name,
                "On" if is_on else "Off",
            )

            if self.hass:
                # Trigger Home Assistant event
                event_data = {
                    "device_name": device_name,
                    "is_on": is_on,
                    "device_type": device_type,
                    "timestamp": datetime.now().isoformat(),
                }

                # Trigger custom event
                self.hass.bus.fire("daybetter_device_switch_changed", event_data)
                _LOGGER.debug(
                    "Triggered Home Assistant event: daybetter_device_switch_changed"
                )

        except Exception as e:
            _LOGGER.error(
                "Error updating Home Assistant device switch status: %s", str(e)
            )

    def _update_device_brightness_in_hass(
        self, device_name: str, brightness: float, device_type: int
    ):
        """Update device brightness status in Home Assistant

        Args:
            device_name: Device unique ID
            brightness: Brightness Value (0~100)
            device_type: Device Type
        """
        try:
            # Log status update
            _LOGGER.debug(
                "Preparing to update device brightness in Home Assistant: %s -> %s%%",
                device_name,
                brightness,
            )

            if self.hass:
                # Trigger Home Assistant event
                event_data = {
                    "device_name": device_name,
                    "brightness": brightness,
                    "device_type": device_type,
                    "timestamp": datetime.now().isoformat(),
                }

                # Trigger custom event
                self.hass.bus.fire("daybetter_device_brightness_changed", event_data)
                _LOGGER.debug(
                    "Triggered Home Assistant event: daybetter_device_brightness_changed"
                )

        except Exception as e:
            _LOGGER.error("Error updating Home Assistant device brightness: %s", str(e))

    def _update_device_color_in_hass(
        self, device_name: str, rgb_color: str, device_type: int
    ):
        """Update device color status in Home Assistant

        Args:
            device_name: Device unique ID
            rgb_color: RGB Color Value (format: #RRGGBB)
            device_type: Device Type
        """
        try:
            # Log status update
            _LOGGER.debug(
                "Preparing to update device color in Home Assistant: %s -> %s",
                device_name,
                rgb_color,
            )

            if self.hass:
                # Trigger Home Assistant event
                event_data = {
                    "device_name": device_name,
                    "rgb_color": rgb_color,
                    "device_type": device_type,
                    "timestamp": datetime.now().isoformat(),
                }

                # Trigger custom event
                self.hass.bus.fire("daybetter_device_color_changed", event_data)
                _LOGGER.debug(
                    "Triggered Home Assistant event: daybetter_device_color_changed"
                )

        except Exception as e:
            _LOGGER.error("Error updating Home Assistant device color: %s", str(e))

    def _update_sensor_data_in_hass(
        self, device_name: str, sensor_type: str, value: float, device_type: int
    ):
        """Update sensor data in Home Assistant

        Args:
            device_name: Device unique ID
            sensor_type: Sensor type (temperature/humidity)
            value: Sensor value
            device_type: Device Type
        """
        try:
            # Log status update
            _LOGGER.debug(
                "Preparing to update sensor data in Home Assistant: %s -> %s = %s",
                device_name,
                sensor_type,
                value,
            )

            if self.hass:
                # Trigger Home Assistant event
                event_data = {
                    "device_name": device_name,
                    "sensor_type": sensor_type,
                    "value": value,
                    "device_type": device_type,
                    "timestamp": datetime.now().isoformat(),
                }

                # Trigger custom event
                self.hass.bus.fire("daybetter_sensor_data_changed", event_data)
                _LOGGER.debug(
                    "Triggered Home Assistant event: daybetter_sensor_data_changed"
                )

        except Exception as e:
            _LOGGER.error("Error updating Home Assistant sensor data: %s", str(e))

    def _trigger_device_status_callbacks(
        self, device_name: str, is_online: bool, device_type: int, topic: str
    ):
        """Trigger device status callback function

        Args:
            device_name: Device unique ID
            is_online: Whether device is online
            device_type: Device Type
            topic: MQTT topic
        """
        try:
            # Use Home Assistant's call_soon_threadsafe method to schedule to event loop
            def safe_callback():
                try:
                    # Trigger general device status callback
                    if "device_status" in self._device_status_callbacks:
                        callback = self._device_status_callbacks["device_status"]
                        callback(device_name, is_online, device_type, topic)

                    # Trigger specific device callback
                    if device_name in self._device_status_callbacks:
                        callback = self._device_status_callbacks[device_name]
                        callback(device_name, is_online, device_type, topic)
                except Exception as e:
                    _LOGGER.error("Error executing device status callback: %s", str(e))

            # Use Home Assistant's event loop to schedule callback
            try:
                # Get Home Assistant's event loop
                if self.hass is not None:
                    # Try to get Home Assistant's event loop
                    hass_loop = None
                    try:
                        # Try different attribute names to get event loop
                        hass_loop = getattr(self.hass, "_loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "asyncio_loop", None)

                        if hass_loop and not hass_loop.is_closed():
                            # Create an async task to execute callback
                            async def async_safe_callback():
                                try:
                                    _LOGGER.info(
                                        "🔄 Async callback task started: %s -> %s",
                                        device_name,
                                        is_online,
                                    )
                                    safe_callback()
                                    _LOGGER.info("✅ Async callback task completed")
                                except Exception as e:
                                    _LOGGER.error(
                                        "❌ Async callback task execution error: %s",
                                        str(e),
                                    )

                            # Use asyncio.run_coroutine_threadsafe to create async task
                            import asyncio

                            future = asyncio.run_coroutine_threadsafe(
                                async_safe_callback(), hass_loop
                            )
                            _LOGGER.debug(
                                "Async callback task scheduled to Home Assistant event loop"
                            )
                        else:
                            _LOGGER.warning(
                                "Unable to get valid Home Assistant event loop, execute callback directly"
                            )
                            safe_callback()
                    except Exception as loop_error:
                        _LOGGER.error(
                            "Error getting Home Assistant event loop: %s",
                            str(loop_error),
                        )
                        safe_callback()
                else:
                    _LOGGER.error(
                        "Home Assistant instance not available, cannot schedule callback"
                    )
                    safe_callback()

            except Exception as e:
                _LOGGER.error("Error scheduling callback to event loop: %s", str(e))
                safe_callback()

        except Exception as e:
            _LOGGER.error("Error triggering device status callback: %s", str(e))

    async def _async_trigger_device_status_callbacks(
        self, device_name: str, is_online: bool, device_type: int, topic: str
    ):
        """Async trigger device status callback function"""
        try:
            # Trigger general device status callback
            if "device_status" in self._device_status_callbacks:
                callback = self._device_status_callbacks["device_status"]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, is_online, device_type, topic)
                else:
                    callback(device_name, is_online, device_type, topic)

            # Trigger specific device callback
            if device_name in self._device_status_callbacks:
                callback = self._device_status_callbacks[device_name]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, is_online, device_type, topic)
                else:
                    callback(device_name, is_online, device_type, topic)

        except Exception as e:
            _LOGGER.error("Error in async trigger device status callback: %s", str(e))

    async def _async_execute_callback(self, callback_func):
        """Async execute callback function"""
        try:
            callback_func()
        except Exception as e:
            _LOGGER.error("Error executing callback function: %s", str(e))

    def _trigger_device_switch_callbacks(
        self, device_name: str, is_on: bool, device_type: int, topic: str
    ):
        """Trigger device switch status callback function

        Args:
            device_name: Device unique ID
            is_on: Whether device is on
            device_type: Device Type
            topic: MQTT topic
        """
        try:
            # Use Home Assistant's call_soon_threadsafe method to schedule to event loop
            def safe_callback():
                try:
                    _LOGGER.info(
                        "🔄 Start executing device switch status callback: %s -> %s",
                        device_name,
                        is_on,
                    )
                    # Trigger general device switch callback
                    if "device_switch" in self._device_status_callbacks:
                        callback = self._device_status_callbacks["device_switch"]
                        _LOGGER.info("🔄 Execute general device switch callback")
                        callback(device_name, is_on, device_type, topic)
                        _LOGGER.info(
                            "✅ General device switch callback execution completed"
                        )

                    # Trigger specific device switch callback
                    switch_key = f"{device_name}_switch"
                    _LOGGER.debug("Looking for callback key: %s", switch_key)
                    _LOGGER.debug(
                        "Currently registered callback keys: %s",
                        list(self._device_status_callbacks.keys()),
                    )
                    if switch_key in self._device_status_callbacks:
                        callback = self._device_status_callbacks[switch_key]
                        _LOGGER.info(
                            "🔄 Execute specific device switch callback: %s", switch_key
                        )
                        callback(device_name, is_on, device_type, topic)
                        _LOGGER.info(
                            "✅ Specific device switch callback execution completed"
                        )
                    else:
                        _LOGGER.warning(
                            "⚠️ Specific device switch callback not found: %s",
                            switch_key,
                        )
                except Exception as e:
                    _LOGGER.error(
                        "❌ Error executing device switch status callback: %s", str(e)
                    )

            # Use Home Assistant's event loop to schedule callback
            try:
                # Get Home Assistant's event loop
                if self.hass is not None:
                    # Try to get Home Assistant's event loop
                    hass_loop = None
                    try:
                        # Try different attribute names to get event loop
                        hass_loop = getattr(self.hass, "_loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "asyncio_loop", None)

                        if hass_loop and not hass_loop.is_closed():
                            # Create an async task to execute callback
                            async def async_safe_callback():
                                try:
                                    _LOGGER.info(
                                        "🔄 Async callback task started executing: %s -> %s",
                                        device_name,
                                        is_on,
                                    )
                                    safe_callback()
                                    _LOGGER.info("✅ Async callback task completed")
                                except Exception as e:
                                    _LOGGER.error(
                                        "❌ Async callback task execution error: %s",
                                        str(e),
                                    )

                            # Use asyncio.run_coroutine_threadsafe to create async task
                            import asyncio

                            future = asyncio.run_coroutine_threadsafe(
                                async_safe_callback(), hass_loop
                            )
                            _LOGGER.debug(
                                "Async callback task scheduled to Home Assistant event loop"
                            )
                        else:
                            _LOGGER.warning(
                                "Unable to get valid Home Assistant event loop, execute callback directly"
                            )
                            safe_callback()
                    except Exception as loop_error:
                        _LOGGER.error(
                            "Error getting Home Assistant event loop: %s",
                            str(loop_error),
                        )
                        safe_callback()
                else:
                    _LOGGER.error(
                        "Home Assistant instance not available, cannot schedule callback"
                    )
                    safe_callback()

            except Exception as e:
                _LOGGER.error("Error scheduling callback to event loop: %s", str(e))
                safe_callback()

        except Exception as e:
            _LOGGER.error("Error triggering device switch status callback: %s", str(e))

    async def _async_trigger_device_switch_callbacks(
        self, device_name: str, is_on: bool, device_type: int, topic: str
    ):
        """Async trigger device switch status callback function"""
        try:
            # Trigger general device switch callback
            if "device_switch" in self._device_status_callbacks:
                callback = self._device_status_callbacks["device_switch"]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, is_on, device_type, topic)
                else:
                    callback(device_name, is_on, device_type, topic)

            # Trigger specific device switch callback
            switch_key = f"{device_name}_switch"
            if switch_key in self._device_status_callbacks:
                callback = self._device_status_callbacks[switch_key]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, is_on, device_type, topic)
                else:
                    callback(device_name, is_on, device_type, topic)

        except Exception as e:
            _LOGGER.error(
                "Error in async trigger device switch status callback: %s", str(e)
            )

    def _trigger_sensor_data_callbacks(
        self,
        device_name: str,
        sensor_type: str,
        value: float,
        device_type: int,
        topic: str,
    ):
        """Trigger sensor data callback function

        Args:
            device_name: Device unique ID
            sensor_type: Sensor type (temperature/humidity)
            value: Sensor value
            device_type: Device Type
            topic: MQTT topic
        """
        try:
            # Use Home Assistant's call_soon_threadsafe method to schedule to event loop
            def safe_callback():
                try:
                    _LOGGER.info(
                        "🔄 Start executing sensor data callback: %s -> %s = %s",
                        device_name,
                        sensor_type,
                        value,
                    )
                    # Trigger general sensor data callback
                    if "sensor_data" in self._device_status_callbacks:
                        callback = self._device_status_callbacks["sensor_data"]
                        _LOGGER.info("🔄 Execute general sensor data callback")
                        callback(device_name, sensor_type, value, device_type, topic)
                        _LOGGER.info(
                            "✅ General sensor data callback execution completed"
                        )

                    # Trigger specific device sensor data callback
                    # First try to find specific sensor type callback
                    specific_sensor_key = f"{device_name}_{sensor_type}"
                    general_sensor_key = f"{device_name}_sensor"

                    _LOGGER.debug(
                        "Looking for specific sensor callback key: %s",
                        specific_sensor_key,
                    )
                    _LOGGER.debug(
                        "Looking for general sensor callback key: %s",
                        general_sensor_key,
                    )
                    _LOGGER.debug(
                        "Currently registered callback keys: %s",
                        list(self._device_status_callbacks.keys()),
                    )

                    callback_found = False

                    # Prioritize finding specific sensor type callback
                    if specific_sensor_key in self._device_status_callbacks:
                        callback = self._device_status_callbacks[specific_sensor_key]
                        _LOGGER.info(
                            "🔄 Execute specific sensor type callback: %s",
                            specific_sensor_key,
                        )
                        callback(device_name, sensor_type, value, device_type, topic)
                        _LOGGER.info(
                            "✅ Specific sensor type callback execution completed"
                        )
                        callback_found = True
                    # If specific type not found, try general sensor callback
                    elif general_sensor_key in self._device_status_callbacks:
                        callback = self._device_status_callbacks[general_sensor_key]
                        _LOGGER.info(
                            "🔄 Execute general sensor callback: %s", general_sensor_key
                        )
                        callback(device_name, sensor_type, value, device_type, topic)
                        _LOGGER.info("✅ General sensor callback execution completed")
                        callback_found = True

                    if not callback_found:
                        _LOGGER.warning(
                            "⚠️ Sensor data callback not found: %s or %s",
                            specific_sensor_key,
                            general_sensor_key,
                        )
                except Exception as e:
                    _LOGGER.error("❌ Error executing sensor data callback: %s", str(e))

            # Use Home Assistant's event loop to schedule callback
            try:
                # Get Home Assistant's event loop
                if self.hass is not None:
                    # Try to get Home Assistant's event loop
                    hass_loop = None
                    try:
                        # Try different attribute names to get event loop
                        hass_loop = getattr(self.hass, "_loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "asyncio_loop", None)

                        if hass_loop and not hass_loop.is_closed():
                            # Create an async task to execute callback
                            async def async_safe_callback():
                                try:
                                    _LOGGER.info(
                                        "🔄 async sensor data callback task started executing: %s -> %s = %s",
                                        device_name,
                                        sensor_type,
                                        value,
                                    )
                                    safe_callback()
                                    _LOGGER.info(
                                        "✅ async sensor data callback task execution completed"
                                    )
                                except Exception as e:
                                    _LOGGER.error(
                                        "❌ async sensor data callback task execution error: %s",
                                        str(e),
                                    )

                            # Use asyncio.run_coroutine_threadsafe to create async task
                            import asyncio

                            future = asyncio.run_coroutine_threadsafe(
                                async_safe_callback(), hass_loop
                            )
                            _LOGGER.debug(
                                "async sensor data callback task scheduled to Home Assistant event loop"
                            )
                        else:
                            _LOGGER.warning(
                                "Unable to get validHome Assistantevent loop，directly execute sensor data callback"
                            )
                            safe_callback()
                    except Exception as loop_error:
                        _LOGGER.error(
                            "Error getting Home Assistant event loop: %s",
                            str(loop_error),
                        )
                        safe_callback()
                else:
                    _LOGGER.error(
                        "Home Assistantinstance not available，unable to schedule sensor data callback"
                    )
                    safe_callback()

            except Exception as e:
                _LOGGER.error(
                    "error scheduling sensor data callback to event loop: %s", str(e)
                )
                safe_callback()

        except Exception as e:
            _LOGGER.error("Error triggering sensor data callback: %s", str(e))

    def _trigger_device_brightness_callbacks(
        self, device_name: str, brightness: float, device_type: int, topic: str
    ):
        """Trigger device brightness change callback function

        Args:
            device_name: Device unique ID
            brightness: Brightness Value (0~100)
            device_type: Device Type
            topic: MQTT topic
        """
        try:
            # Use Home Assistant's call_soon_threadsafe method to schedule to event loop
            def safe_callback():
                try:
                    _LOGGER.info(
                        "🔄 Start executing device brightness callback: %s -> %s%%",
                        device_name,
                        brightness,
                    )
                    # Trigger general device brightness callback
                    if "device_brightness" in self._device_status_callbacks:
                        callback = self._device_status_callbacks["device_brightness"]
                        _LOGGER.info("🔄 Execute general device brightness callback")
                        callback(device_name, brightness, device_type, topic)
                        _LOGGER.info(
                            "✅ General device brightness callback execution completed"
                        )

                    # Trigger specific device brightness callback
                    brightness_key = f"{device_name}_brightness"
                    _LOGGER.debug("Looking for callback key: %s", brightness_key)
                    _LOGGER.debug(
                        "Currently registered callback keys: %s",
                        list(self._device_status_callbacks.keys()),
                    )
                    if brightness_key in self._device_status_callbacks:
                        callback = self._device_status_callbacks[brightness_key]
                        _LOGGER.info(
                            "🔄 Execute specific device brightness callback: %s",
                            brightness_key,
                        )
                        callback(device_name, brightness, device_type, topic)
                        _LOGGER.info(
                            "✅ specificDevice brightness callback execution completed"
                        )
                    else:
                        _LOGGER.warning(
                            "⚠️ No specific device brightness callback found: %s",
                            brightness_key,
                        )
                except Exception as e:
                    _LOGGER.error(
                        "❌ Executing device brightness callback error occurred: %s",
                        str(e),
                    )

            # Use Home Assistant's event loop to schedule callback
            try:
                # Get Home Assistant's event loop
                if self.hass is not None:
                    # Try to get Home Assistant's event loop
                    hass_loop = None
                    try:
                        # Try different attribute names to get event loop
                        hass_loop = getattr(self.hass, "_loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "asyncio_loop", None)

                        if hass_loop and not hass_loop.is_closed():
                            # Create an async task to execute callback
                            async def async_safe_callback():
                                try:
                                    _LOGGER.info(
                                        "🔄 async brightness callback task started executing: %s -> %s%%",
                                        device_name,
                                        brightness,
                                    )
                                    safe_callback()
                                    _LOGGER.info(
                                        "✅ Async brightness callback task execution completed"
                                    )
                                except Exception as e:
                                    _LOGGER.error(
                                        "❌ Async brightness callback task execution error: %s",
                                        str(e),
                                    )

                            # Use asyncio.run_coroutine_threadsafe to create async task
                            import asyncio

                            future = asyncio.run_coroutine_threadsafe(
                                async_safe_callback(), hass_loop
                            )
                            _LOGGER.debug(
                                "async brightness callback task scheduled to Home Assistant event loop"
                            )
                        else:
                            _LOGGER.warning(
                                "Unable to get validHome Assistantevent loop，directly execute brightness callback"
                            )
                            safe_callback()
                    except Exception as loop_error:
                        _LOGGER.error(
                            "Error getting Home Assistant event loop: %s",
                            str(loop_error),
                        )
                        safe_callback()
                else:
                    _LOGGER.error(
                        "Home Assistantinstance not available，unable to schedule brightness callback"
                    )
                    safe_callback()

            except Exception as e:
                _LOGGER.error(
                    "error scheduling brightness callback to event loop: %s", str(e)
                )
                safe_callback()

        except Exception as e:
            _LOGGER.error(
                "Trigger device brightness callbackerror occurred: %s", str(e)
            )

    async def _async_trigger_device_brightness_callbacks(
        self, device_name: str, brightness: float, device_type: int, topic: str
    ):
        """Async trigger device brightness change callback function"""
        try:
            # Trigger general device brightness callback
            if "device_brightness" in self._device_status_callbacks:
                callback = self._device_status_callbacks["device_brightness"]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, brightness, device_type, topic)
                else:
                    callback(device_name, brightness, device_type, topic)

            # Trigger specific device brightness callback
            brightness_key = f"{device_name}_brightness"
            if brightness_key in self._device_status_callbacks:
                callback = self._device_status_callbacks[brightness_key]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, brightness, device_type, topic)
                else:
                    callback(device_name, brightness, device_type, topic)

        except Exception as e:
            _LOGGER.error(
                "asyncTrigger device brightness callbackerror occurred: %s", str(e)
            )

    def _trigger_device_color_callbacks(
        self, device_name: str, rgb_color: str, device_type: int, topic: str
    ):
        """Trigger device color change callback function

        Args:
            device_name: Device unique ID
            rgb_color: RGB Color Value (format: #RRGGBB)
            device_type: Device Type
            topic: MQTT topic
        """
        try:
            # Use Home Assistant's call_soon_threadsafe method to schedule to event loop
            def safe_callback():
                try:
                    _LOGGER.info(
                        "🔄 Start executing device color callback: %s -> %s",
                        device_name,
                        rgb_color,
                    )
                    # Trigger general device color callback
                    if "device_color" in self._device_status_callbacks:
                        callback = self._device_status_callbacks["device_color"]
                        _LOGGER.info("🔄 Execute general device color callback")
                        callback(device_name, rgb_color, device_type, topic)
                        _LOGGER.info(
                            "✅ General device color callback execution completed"
                        )

                    # Trigger specific device color callback
                    color_key = f"{device_name}_color"
                    _LOGGER.debug("Looking for callback key: %s", color_key)
                    _LOGGER.debug(
                        "Currently registered callback keys: %s",
                        list(self._device_status_callbacks.keys()),
                    )
                    if color_key in self._device_status_callbacks:
                        callback = self._device_status_callbacks[color_key]
                        _LOGGER.info(
                            "🔄 Execute specific device color callback: %s", color_key
                        )
                        callback(device_name, rgb_color, device_type, topic)
                        _LOGGER.info(
                            "✅ specificDevice color callback execution completed"
                        )
                    else:
                        _LOGGER.warning(
                            "⚠️ No specific device color callback found: %s", color_key
                        )
                except Exception as e:
                    _LOGGER.error(
                        "❌ Executing device color callback error occurred: %s", str(e)
                    )

            # Use Home Assistant's event loop to schedule callback
            try:
                # Get Home Assistant's event loop
                if self.hass is not None:
                    # Try to get Home Assistant's event loop
                    hass_loop = None
                    try:
                        # Try different attribute names to get event loop
                        hass_loop = getattr(self.hass, "_loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "loop", None)
                        if hass_loop is None:
                            hass_loop = getattr(self.hass, "asyncio_loop", None)

                        if hass_loop and not hass_loop.is_closed():
                            # Create an async task to execute callback
                            async def async_safe_callback():
                                try:
                                    _LOGGER.info(
                                        "🔄 async color callback task started executing: %s -> %s",
                                        device_name,
                                        rgb_color,
                                    )
                                    safe_callback()
                                    _LOGGER.info(
                                        "✅ Async color callback task execution completed"
                                    )
                                except Exception as e:
                                    _LOGGER.error(
                                        "❌ Async color callback task execution error: %s",
                                        str(e),
                                    )

                            # Use asyncio.run_coroutine_threadsafe to create async task
                            import asyncio

                            future = asyncio.run_coroutine_threadsafe(
                                async_safe_callback(), hass_loop
                            )
                            _LOGGER.debug(
                                "async color callback task scheduled to Home Assistant event loop"
                            )
                        else:
                            _LOGGER.warning(
                                "Unable to get validHome Assistantevent loop，directly execute the color callback"
                            )
                            safe_callback()
                    except Exception as loop_error:
                        _LOGGER.error(
                            "Error getting Home Assistant event loop: %s",
                            str(loop_error),
                        )
                        safe_callback()
                else:
                    _LOGGER.error(
                        "Home Assistantinstance not available，Unable to dispatch color callback"
                    )
                    safe_callback()

            except Exception as e:
                _LOGGER.error(
                    "error scheduling color callback to event loop: %s", str(e)
                )
                safe_callback()

        except Exception as e:
            _LOGGER.error("Trigger device color callbackerror occurred: %s", str(e))

    async def _async_trigger_device_color_callbacks(
        self, device_name: str, rgb_color: str, device_type: int, topic: str
    ):
        """Async trigger device color change callback function"""
        try:
            # Trigger general device color callback
            if "device_color" in self._device_status_callbacks:
                callback = self._device_status_callbacks["device_color"]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, rgb_color, device_type, topic)
                else:
                    callback(device_name, rgb_color, device_type, topic)

            # Trigger specific device color callback
            color_key = f"{device_name}_color"
            if color_key in self._device_status_callbacks:
                callback = self._device_status_callbacks[color_key]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, rgb_color, device_type, topic)
                else:
                    callback(device_name, rgb_color, device_type, topic)

        except Exception as e:
            _LOGGER.error(
                "asyncTrigger device color callbackerror occurred: %s", str(e)
            )

    async def _async_trigger_sensor_data_callbacks(
        self,
        device_name: str,
        sensor_type: str,
        value: float,
        device_type: int,
        topic: str,
    ):
        """Async trigger sensor data callback function"""
        try:
            # Trigger general sensor data callback
            if "sensor_data" in self._device_status_callbacks:
                callback = self._device_status_callbacks["sensor_data"]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, sensor_type, value, device_type, topic)
                else:
                    callback(device_name, sensor_type, value, device_type, topic)

            # Trigger specific device sensor data callback
            sensor_key = f"{device_name}_sensor"
            if sensor_key in self._device_status_callbacks:
                callback = self._device_status_callbacks[sensor_key]
                if asyncio.iscoroutinefunction(callback):
                    await callback(device_name, sensor_type, value, device_type, topic)
                else:
                    callback(device_name, sensor_type, value, device_type, topic)

        except Exception as e:
            _LOGGER.error("Error in async trigger sensor data callback: %s", str(e))

    def register_device_status_callback(
        self, callback: Callable, device_name: str | None = None
    ):
        """Register device status change callback function

        Args:
            callback: callback function，Receive parameters (device_name, is_online, device_type, topic)
            device_name: specific_device_name，if isNonethen register general callback
        """
        try:
            if device_name:
                self._device_status_callbacks[device_name] = callback
                _LOGGER.debug("alreadyRegister device %s status callback", device_name)
            else:
                self._device_status_callbacks["device_status"] = callback
                _LOGGER.debug("Already registered general device status callback")

        except Exception as e:
            _LOGGER.error("Register device status callbackerror occurred: %s", str(e))

    def register_device_switch_callback(
        self, callback: Callable, device_name: str | None = None
    ):
        """Register deviceSwitch Statuschange callback function

        Args:
            callback: callback function，Receive parameters (device_name, is_on, device_type, topic)
            device_name: specific_device_name，if isNonethen register general callback
        """
        try:
            if device_name:
                switch_key = f"{device_name}_switch"
                self._device_status_callbacks[switch_key] = callback
                _LOGGER.debug(
                    "alreadyRegister device %s Switch Statuscallback，key name: %s",
                    device_name,
                    switch_key,
                )
                _LOGGER.debug(
                    "All currently registered callback keys: %s",
                    list(self._device_status_callbacks.keys()),
                )
            else:
                self._device_status_callbacks["device_switch"] = callback
                _LOGGER.debug(
                    "Already registered general device Switch Status callback"
                )

        except Exception as e:
            _LOGGER.error(
                "Register deviceSwitch Statuscallbackerror occurred: %s", str(e)
            )

    def register_device_brightness_callback(
        self, callback: Callable, device_name: str | None = None
    ):
        """Register device brightness change callback function

        Args:
            callback: callback function，Receive parameters (device_name, brightness, device_type, topic)
            device_name: specific_device_name，if isNonethen register general callback
        """
        try:
            if device_name:
                brightness_key = f"{device_name}_brightness"
                self._device_status_callbacks[brightness_key] = callback
                _LOGGER.debug(
                    "alreadyRegister device %s brightness callback，key name: %s",
                    device_name,
                    brightness_key,
                )
                _LOGGER.debug(
                    "All currently registered callback keys: %s",
                    list(self._device_status_callbacks.keys()),
                )
            else:
                self._device_status_callbacks["device_brightness"] = callback
                _LOGGER.debug("Already registered generic device brightness callback")

        except Exception as e:
            _LOGGER.error(
                "Register device brightness callbackerror occurred: %s", str(e)
            )

    def register_device_color_callback(
        self, callback: Callable, device_name: str | None = None
    ):
        """Register device color change callback function

        Args:
            callback: callback function，Receive parameters (device_name, rgb_color, device_type, topic)
            device_name: specific_device_name，if isNonethen register general callback
        """
        try:
            if device_name:
                color_key = f"{device_name}_color"
                self._device_status_callbacks[color_key] = callback
                _LOGGER.debug(
                    "alreadyRegister device %s color callback，key name: %s",
                    device_name,
                    color_key,
                )
                _LOGGER.debug(
                    "All currently registered callback keys: %s",
                    list(self._device_status_callbacks.keys()),
                )
            else:
                self._device_status_callbacks["device_color"] = callback
                _LOGGER.debug("Already registered generic device color callback")

        except Exception as e:
            _LOGGER.error("Register device color callbackerror occurred: %s", str(e))

    def unregister_device_status_callback(self, device_name: str | None = None):
        """CancelRegister device status change callback function

        Args:
            device_name: specific_device_name，if isNonethen cancel general callback
        """
        try:
            if device_name and device_name in self._device_status_callbacks:
                del self._device_status_callbacks[device_name]
                _LOGGER.debug(
                    "alreadycancelRegister device %s status callback", device_name
                )
            elif not device_name and "device_status" in self._device_status_callbacks:
                del self._device_status_callbacks["device_status"]
                _LOGGER.debug("already cancel register general device status callback")

        except Exception as e:
            _LOGGER.error(
                "cancelRegister device status callbackerror occurred: %s", str(e)
            )

    def unregister_device_switch_callback(self, device_name: str | None = None):
        """CancelRegister deviceSwitch Statuschange callback function

        Args:
            device_name: specific_device_name，if isNonethen cancel general callback
        """
        try:
            if device_name:
                switch_key = f"{device_name}_switch"
                if switch_key in self._device_status_callbacks:
                    del self._device_status_callbacks[switch_key]
                    _LOGGER.debug(
                        "alreadycancelRegister device %s Switch Statuscallback",
                        device_name,
                    )
            elif "device_switch" in self._device_status_callbacks:
                del self._device_status_callbacks["device_switch"]
                _LOGGER.debug(
                    "already cancel registration of universal device Switch Status callback"
                )

        except Exception as e:
            _LOGGER.error(
                "cancelRegister deviceSwitch Statuscallbackerror occurred: %s", str(e)
            )

    def unregister_device_brightness_callback(self, device_name: str | None = None):
        """CancelRegister device brightness change callback function

        Args:
            device_name: specific_device_name，if isNonethen cancel general callback
        """
        try:
            if device_name:
                brightness_key = f"{device_name}_brightness"
                if brightness_key in self._device_status_callbacks:
                    del self._device_status_callbacks[brightness_key]
                    _LOGGER.debug(
                        "alreadycancelRegister device %s brightness callback",
                        device_name,
                    )
            elif "device_brightness" in self._device_status_callbacks:
                del self._device_status_callbacks["device_brightness"]
                _LOGGER.debug(
                    "alreadycancel register universal device brightness callback"
                )

        except Exception as e:
            _LOGGER.error(
                "cancelRegister device brightness callbackerror occurred: %s", str(e)
            )

    def unregister_device_color_callback(self, device_name: str | None = None):
        """CancelRegister device color change callback function

        Args:
            device_name: specific_device_name，if isNonethen cancel general callback
        """
        try:
            if device_name:
                color_key = f"{device_name}_color"
                if color_key in self._device_status_callbacks:
                    del self._device_status_callbacks[color_key]
                    _LOGGER.debug(
                        "alreadycancelRegister device %s color callback", device_name
                    )
            elif "device_color" in self._device_status_callbacks:
                del self._device_status_callbacks["device_color"]
                _LOGGER.debug("alreadycancel register universal device color callback")

        except Exception as e:
            _LOGGER.error(
                "cancelRegister device color callbackerror occurred: %s", str(e)
            )

    def register_sensor_data_callback(
        self, callback: Callable, device_name: str | None = None
    ):
        """Register sensor data change callback function

        Args:
            callback: callback function，Receive parameters (device_name, sensor_type, value, device_type, topic)
            device_name: specific device name or sensor key name，if isNonethen register general callback
        """
        try:
            if device_name:
                # Directly use the incoming device name as the key name（may already contain_temperatureor_humiditysuffix）
                self._device_status_callbacks[device_name] = callback
                _LOGGER.debug(
                    "alreadyRegister sensor data callback，key name: %s", device_name
                )
                _LOGGER.debug(
                    "All currently registered callback keys: %s",
                    list(self._device_status_callbacks.keys()),
                )
            else:
                self._device_status_callbacks["sensor_data"] = callback
                _LOGGER.debug("Already registered general sensor data callback")

        except Exception as e:
            _LOGGER.error("Register sensor data callbackerror occurred: %s", str(e))

    def unregister_sensor_data_callback(self, device_name: str | None = None):
        """Cancel register sensor data change callback function

        Args:
            device_name: specific_device_name，if isNonethen cancel general callback
        """
        try:
            if device_name:
                sensor_key = f"{device_name}_sensor"
                if sensor_key in self._device_status_callbacks:
                    del self._device_status_callbacks[sensor_key]
                    _LOGGER.debug(
                        "alreadycancelRegister device %s sensor data callback",
                        device_name,
                    )
            elif "sensor_data" in self._device_status_callbacks:
                del self._device_status_callbacks["sensor_data"]
                _LOGGER.debug("already cancel register general sensor data callback")

        except Exception as e:
            _LOGGER.error(
                "cancelRegister sensor data callbackerror occurred: %s", str(e)
            )

    def register_message_callback(self, topic_pattern: str, callback: Callable):
        """Register a message callback function

        Args:
            topic_pattern: Topicmode
            callback: callback function，Receive parameters (topic, payload, data)
        """
        try:
            self._message_callbacks[topic_pattern] = callback
            _LOGGER.debug("Topic %s message callback already registered", topic_pattern)

        except Exception as e:
            _LOGGER.error("Registration message callback error occurred: %s", str(e))

    def unregister_message_callback(self, topic_pattern: str):
        """Cancel registration message callback function

        Args:
            topic_pattern: Topicmode
        """
        try:
            if topic_pattern in self._message_callbacks:
                del self._message_callbacks[topic_pattern]
                _LOGGER.debug(
                    "Already canceled registration of Topic %s message callback",
                    topic_pattern,
                )

        except Exception as e:
            _LOGGER.error(
                "cancel registration message callbackerror occurred: %s", str(e)
            )

    def get_device_status(self, device_name: str) -> dict[str, Any] | None:
        """Get device status information

        Args:
            device_name: Device name

        Returns:
            Dict: Device status information，Return if device does not existNone
        """
        # Device status caching logic can be implemented here
        # Currently returnsNone，indicates need to get fromMQTTGet real-time status from message
        return None

    def cleanup(self):
        """Clean up resources"""
        try:
            self._device_status_callbacks.clear()
            self._message_callbacks.clear()
            _LOGGER.debug("Message processor resources are already cleaned up")

        except Exception as e:
            _LOGGER.error(
                "Cleaning up message processor resources error occurred: %s", str(e)
            )
