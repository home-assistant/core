"""API wrapper for Wireless Sensor Tag."""

from __future__ import annotations

import logging
from typing import Any

from wirelesstagpy import WirelessTags
from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class WirelessTagAPI:
    """API wrapper for Wireless Sensor Tag."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Initialize the API wrapper."""
        self._hass = hass
        self._username = username
        self._password = password
        self._tags_api: WirelessTags | None = None

    async def async_authenticate(self) -> bool:
        """Authenticate with the Wireless Sensor Tag API."""
        try:
            # Create API instance with executor job
            self._tags_api = await self._hass.async_add_executor_job(
                WirelessTags, self._username, self._password
            )
        except (WirelessTagsException, Exception) as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False
        else:
            return True

    async def async_get_tags(self) -> dict[str, Any]:
        """Get all tags from the API."""
        if not self._tags_api:
            raise HomeAssistantError("API not authenticated")

        try:
            tags = await self._hass.async_add_executor_job(self._tags_api.load_tags)
        except WirelessTagsException as err:
            _LOGGER.error("Failed to get tags: %s", err)
            raise HomeAssistantError(f"Failed to get tags: {err}") from err
        else:
            return tags

    async def async_arm_tag(self, tag_id: str, mac: str, sensor_type: str) -> bool:
        """Arm wireless tag sensor."""
        _LOGGER.debug(
            "Attempting to arm tag %s (MAC: %s) for sensor type: %s",
            tag_id,
            mac,
            sensor_type,
        )
        try:
            # Get the specific arm method for this sensor type
            arm_method_name = f"arm_{sensor_type}"
            if not hasattr(self._tags_api, arm_method_name):
                _LOGGER.error(
                    "Sensor type '%s' not supported for arm operation", sensor_type
                )
                return False

            arm_method = getattr(self._tags_api, arm_method_name)
            result = await self._hass.async_add_executor_job(arm_method, tag_id, mac)
        except WirelessTagsException as e:
            _LOGGER.error("Failed to arm tag %s sensor %s: %s", tag_id, sensor_type, e)
            return False
        else:
            _LOGGER.debug(
                "Arm result for tag %s sensor %s: %s (type: %s)",
                tag_id,
                sensor_type,
                result,
                type(result),
            )
            # Check if result is the literal string 'd' which indicates API failure
            if result == "d":
                _LOGGER.warning(
                    "API returned 'd' for arm operation on tag %s sensor %s - this may indicate an API issue",
                    tag_id,
                    sensor_type,
                )
                return False
            return bool(result)

    async def async_disarm_tag(self, tag_id: str, mac: str, sensor_type: str) -> bool:
        """Disarm wireless tag sensor."""
        _LOGGER.debug(
            "Attempting to disarm tag %s (MAC: %s) for sensor type: %s",
            tag_id,
            mac,
            sensor_type,
        )
        try:
            # Get the specific disarm method for this sensor type
            disarm_method_name = f"disarm_{sensor_type}"
            if not hasattr(self._tags_api, disarm_method_name):
                _LOGGER.error(
                    "Sensor type '%s' not supported for disarm operation", sensor_type
                )
                return False

            disarm_method = getattr(self._tags_api, disarm_method_name)
            result = await self._hass.async_add_executor_job(disarm_method, tag_id, mac)
        except WirelessTagsException as e:
            _LOGGER.error(
                "Failed to disarm tag %s sensor %s: %s", tag_id, sensor_type, e
            )
            return False
        else:
            _LOGGER.debug(
                "Disarm result for tag %s sensor %s: %s (type: %s)",
                tag_id,
                sensor_type,
                result,
                type(result),
            )
            # Check if result is the literal string 'd' which indicates API failure
            if result == "d":
                _LOGGER.warning(
                    "API returned 'd' for disarm operation on tag %s sensor %s - this may indicate an API issue",
                    tag_id,
                    sensor_type,
                )
                return False
            return bool(result)

    async def async_start_monitoring(self, callback) -> None:
        """Start monitoring for push events."""
        if not self._tags_api:
            raise HomeAssistantError("API not authenticated")

        # Create a thread-safe wrapper for the callback
        def thread_safe_callback(*args, **kwargs):
            """Wrapper to make callback thread-safe."""
            # Schedule the callback to run in the Home Assistant event loop
            self._hass.loop.call_soon_threadsafe(callback, *args, **kwargs)

        await self._hass.async_add_executor_job(
            self._tags_api.start_monitoring, thread_safe_callback
        )
