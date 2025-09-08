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

    async def async_arm_tag(self, tag_id: str, tag_mac: str, sensor_type: str) -> bool:
        """Arm a tag sensor."""
        if not self._tags_api:
            raise HomeAssistantError("API not authenticated")

        func_name = f"arm_{sensor_type}"
        arm_func = getattr(self._tags_api, func_name, None)
        if not arm_func:
            _LOGGER.error("Arm function not found for sensor type: %s", sensor_type)
            return False

        try:
            await self._hass.async_add_executor_job(arm_func, tag_id, tag_mac)
        except WirelessTagsException as err:
            _LOGGER.error("Failed to arm tag %s: %s", tag_id, err)
            return False
        else:
            return True

    async def async_disarm_tag(
        self, tag_id: str, tag_mac: str, sensor_type: str
    ) -> bool:
        """Disarm a tag sensor."""
        if not self._tags_api:
            raise HomeAssistantError("API not authenticated")

        func_name = f"disarm_{sensor_type}"
        disarm_func = getattr(self._tags_api, func_name, None)
        if not disarm_func:
            _LOGGER.error("Disarm function not found for sensor type: %s", sensor_type)
            return False

        try:
            await self._hass.async_add_executor_job(disarm_func, tag_id, tag_mac)
        except WirelessTagsException as err:
            _LOGGER.error("Failed to disarm tag %s: %s", tag_id, err)
            return False
        else:
            return True

    async def async_start_monitoring(self, callback) -> None:
        """Start monitoring for push events."""
        if not self._tags_api:
            raise HomeAssistantError("API not authenticated")

        await self._hass.async_add_executor_job(
            self._tags_api.start_monitoring, callback
        )
