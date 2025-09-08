"""DataUpdateCoordinator for Wireless Sensor Tags."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WirelessTagAPI
from .const import DEFAULT_TAG_NAME, DEFAULT_UUID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class WirelessTagDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Wireless Tag API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: WirelessTagAPI,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            config_entry=config_entry,
        )
        self.api = api
        self.config_entry = config_entry
        self._monitoring_started = False
        self._initial_update = True
        self.new_devices_callbacks: list[Callable[[set[str]], None]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            tags_data = await self.api.async_get_tags()

            # Transform API data into our expected format
            transformed_data = {
                tag_id: self._transform_tag_data(tag_data)
                for tag_id, tag_data in tags_data.items()
            }

            # Dynamically add new devices if new tags are detected (but skip on initial update)
            if not self._initial_update:
                existing_tag_ids = set(self.data.keys()) if self.data else set()
                new_tag_ids = set(tags_data.keys()) - existing_tag_ids
                if new_tag_ids and self.config_entry is not None:
                    await self._async_add_dynamic_devices(
                        self.config_entry, new_tag_ids
                    )
            else:
                self._initial_update = False

            # Remove stale devices that are no longer present
            await self._async_remove_stale_devices(set(tags_data.keys()))

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            # Start monitoring on first successful data fetch
            if not self._monitoring_started:
                await self.api.async_start_monitoring(self._handle_push_callback)
                self._monitoring_started = True

            return transformed_data

    async def _async_remove_stale_devices(self, current_tag_ids: set[str]) -> None:
        """Remove devices that are no longer present in the account."""
        if self.config_entry is None:
            return

        device_registry = dr.async_get(self.hass)

        # Get all devices registered by this config entry
        devices = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )

        for device in devices:
            # Extract tag ID from device identifiers
            tag_id = None
            for identifier_domain, identifier_value in device.identifiers:
                if identifier_domain == DOMAIN:
                    tag_id = identifier_value
                    break

            if tag_id and tag_id not in current_tag_ids:
                _LOGGER.info(
                    "Removing stale device for tag %s (%s) - no longer present in account",
                    tag_id,
                    device.name or "Unknown",
                )
                # We already checked self.config_entry is not None above
                assert self.config_entry is not None
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )

    async def _async_add_dynamic_devices(
        self, config_entry: ConfigEntry, new_tag_ids: set[str]
    ) -> None:
        """Add new devices dynamically when new tags are detected."""
        _LOGGER.info(
            "Detected new tags: %s - adding entities dynamically",
            ", ".join(new_tag_ids),
        )

        # Call all registered callbacks to add entities for new devices
        for callback in self.new_devices_callbacks:
            callback(new_tag_ids)
        # Note: In a real deployment, new tags would be detected and entities created
        # when the integration is reloaded or Home Assistant is restarted.
        # For now, we just log the detection - the entities will be created
        # when the platforms run their setup again.

    def _handle_push_callback(self, *args, **kwargs) -> None:
        """Handle push notification callback from API."""
        _LOGGER.debug(
            "Received push notification with args: %s, kwargs: %s", args, kwargs
        )
        # Trigger a coordinator refresh to update all entities
        self.async_set_updated_data(self.data)

    def _convert_battery_percentage(
        self, battery_decimal: float | None
    ) -> float | None:
        """Convert battery decimal (0.0-1.0) to percentage (0-100)."""
        if battery_decimal is None:
            return None
        # Convert from decimal (0.95) to percentage (95.0)
        return round(battery_decimal * 100, 1)

    def _convert_humidity_float(self, humidity_float: float | None) -> float | None:
        """Convert humidity float (1.12345) to decimal (1.1)."""
        if humidity_float is None:
            return None
        # Convert from float (1.12345) to decimal (1.1)
        return round(humidity_float, 1)

    def _transform_tag_data(self, tag_data: Any) -> dict[str, Any]:
        """Transform tag data from API format to our internal format."""

        # This transforms the raw API response into a consistent dict format
        # that our entities can easily consume
        def safe_get(data, key, default=None):
            """Safely get value from dict or object attribute."""
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)

        return {
            "name": safe_get(tag_data, "name", DEFAULT_TAG_NAME),
            "uuid": safe_get(tag_data, "uuid", DEFAULT_UUID),
            "is_alive": safe_get(tag_data, "is_alive", False),
            "version": safe_get(tag_data, "version", None),
            # Sensor values
            "temperature": safe_get(tag_data, "temperature", None),
            "humidity": self._convert_humidity_float(
                safe_get(tag_data, "humidity", None)
            ),
            "battery": self._convert_battery_percentage(
                safe_get(tag_data, "battery_remaining", None)
            ),
            "voltage": safe_get(tag_data, "battery_volts", None),
            # Binary sensor states
            "motion": safe_get(tag_data, "motion_detected", None),
            "presence": safe_get(tag_data, "presence_detected", None),
            "door": safe_get(tag_data, "door_opened", None),
            "moisture": safe_get(tag_data, "moisture_detected", None),
            "cold": safe_get(tag_data, "too_cold", None),
            "heat": safe_get(tag_data, "too_hot", None),
            "light": safe_get(tag_data, "light_detected", None),
            # Switch states (armed/disarmed)
            "temperature_armed": safe_get(
                tag_data, "is_temperature_sensor_armed", False
            ),
            "humidity_armed": safe_get(tag_data, "is_humidity_sensor_armed", False),
            "motion_armed": safe_get(tag_data, "is_motion_sensor_armed", False),
            "light_armed": safe_get(tag_data, "is_light_sensor_armed", False),
            "moisture_armed": safe_get(tag_data, "is_moisture_sensor_armed", False),
            # Device info
            "mac": safe_get(tag_data, "tag_manager_mac", None),
            "signal_strength": safe_get(tag_data, "signal_strength", None),
            "power_consumption": safe_get(tag_data, "power_consumption", None),
            "is_in_range": safe_get(tag_data, "is_in_range", True),
        }

    async def async_arm_tag(self, tag_id: str, sensor_type: str) -> bool:
        """Arm a tag sensor."""
        if not self.data:
            return False

        tag_data = self.data.get(tag_id)
        if not tag_data:
            raise ValueError(f"Tag {tag_id} not found")

        mac = tag_data.get("mac")
        if not mac:
            raise ValueError(f"MAC address not found for tag {tag_id}")

        success = await self.api.async_arm_tag(tag_id, mac, sensor_type)
        if success:
            await self.async_request_refresh()
        return success

    async def async_disarm_tag(self, tag_id: str, sensor_type: str) -> bool:
        """Disarm a tag sensor."""
        if not self.data:
            return False

        tag_data = self.data.get(tag_id)
        if not tag_data:
            raise ValueError(f"Tag {tag_id} not found")

        mac = tag_data.get("mac")
        if not mac:
            raise ValueError(f"MAC address not found for tag {tag_id}")

        success = await self.api.async_disarm_tag(tag_id, mac, sensor_type)
        if success:
            await self.async_request_refresh()
        return success
