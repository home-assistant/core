"""Data update coordinator for Heiman integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from heimanconnect import (
    DeviceManagement,
    DeviceProperty,
    HeimanConnectionError,
    HeimanDevice,
    HeimanHome,
    HeimanMqttClient,
    HeimanMQTTError,
    HeimanUser,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeimanApiClient
from .const import CONF_HOME_ID, CONF_USER_ID

_LOGGER = logging.getLogger(__name__)

# Polling interval: 30 minutes
# MQTT handles real-time property updates, but we need periodic polling for:
# - Device online/offline status
# - New device detection
# - Firmware version updates
UPDATE_INTERVAL = timedelta(minutes=30)





@dataclass
class HeimanData:
    """Container for Heiman data."""

    user_info: HeimanUser | None = None
    home_info: HeimanHome | None = None
    devices: dict[str, HeimanDevice] = field(default_factory=dict)
    last_update: datetime | None = None
    errors: dict[str, str] = field(default_factory=dict)


async def _async_call_cleanup_method(
    target: object, method_names: tuple[str, ...]
) -> None:
    """Call the first available cleanup method on a target."""
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if method is None:
            continue
        result = method()
        if hasattr(result, "__await__"):
            await result
        return


class HeimanDataUpdateCoordinator(DataUpdateCoordinator[HeimanData]):
    """Heiman data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api_client: HeimanApiClient,
        config_entry: ConfigEntry,
        device_management: DeviceManagement | None = None,
        oauth_session=None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            logger: Logger instance
            api_client: API client instance
            config_entry: Config entry instance
            device_management: Device management instance
            oauth_session: OAuth2 session for token retrieval
        """
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name="Heiman Home",
            update_interval=UPDATE_INTERVAL,
        )

        self.api_client = api_client
        self.config_entry = config_entry
        self.device_management = device_management
        self.data = HeimanData()
        self.mqtt_client: HeimanMqttClient | None = None
        self.oauth_session = oauth_session
        # Cache for device details to avoid N+1 API calls (managed by SDK)
        self._device_detail_cache: dict[str, dict[str, Any] | None] = {}
        # Cache TTL: 5 minutes
        self._device_detail_cache_ttl = 300

    async def _async_update_data(self) -> HeimanData:
        """Update coordinator data."""
        # Ensure client is initialized
        await self.api_client._ensure_initialized()  # noqa: SLF001

        # Get home ID
        home_id = self.config_entry.data.get(CONF_HOME_ID)
        if not home_id:
            msg = "Home ID not found in config entry"
            raise UpdateFailed(msg)

        # Clear errors at the start of update, then repopulate as we go
        self.data.errors.clear()

        # Fetch user and home info on first update
        await self._fetch_user_and_home_info()

        # Get and process devices
        await self._fetch_and_process_devices(home_id)

        # Update last update time
        self.data.last_update = datetime.now(UTC)

        return self.data

    async def _fetch_user_and_home_info(self) -> None:
        """Fetch user and home information on first update."""
        cloud_wrapper = self.api_client.cloud_client

        # Get user info (only on first update)
        if self.data.user_info is None:
            try:
                self.data.user_info = await cloud_wrapper.async_get_user_info()
            except HeimanConnectionError as err:
                raise UpdateFailed(f"Connection error: {err}") from err
            except Exception as err:
                _LOGGER.error("Failed to fetch user info: %s", err)
                raise UpdateFailed(f"Failed to fetch user info: {err}") from err

        # Get home info (only on first update)
        if self.data.home_info is None:
            try:
                homes = await cloud_wrapper.async_get_homes()
                if homes:
                    home_id = self.config_entry.data.get(CONF_HOME_ID)
                    self.data.home_info = next(
                        (h for h in homes if h.home_id == home_id),
                        homes[0],
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to fetch home info: %s", err)
                self.data.errors["home_info"] = str(err)

    async def _fetch_and_process_devices(self, home_id: str) -> None:
        """Fetch and process device data."""
        cloud_wrapper = self.api_client.cloud_client

        try:
            devices_dict = await cloud_wrapper.async_get_devices(home_id=home_id)

            # Apply device filtering
            if self.device_management:
                devices_list = list(devices_dict.values())
                filtered_devices_list = (
                    self.device_management.filter_manager.get_filtered_devices(
                        devices_list
                    )
                )
                # Convert back to dictionary
                devices = {d.device_id: d for d in filtered_devices_list}
            else:
                devices = devices_dict

            # Get detailed info for filtered devices to populate property values
            await self._update_device_details(devices)

            # Update device data and merge old states
            self._merge_device_states(devices)

        except HeimanConnectionError as err:
            self.data.errors["devices"] = str(err)
            if not self.data.devices:
                raise UpdateFailed(f"Connection error fetching devices: {err}") from err
        except Exception as err:
            _LOGGER.exception("Failed to fetch devices")
            self.data.errors["devices"] = str(err)
            # If there was previous device data, keep it
            if not self.data.devices:
                raise UpdateFailed(f"Failed to fetch devices: {err}") from err

    async def _update_device_details(self, devices: dict[str, HeimanDevice]) -> None:
        """Update device details including properties from deriveMetadata.

        Uses the SDK's batch processing method with caching and concurrency control.
        Cache is invalidated every 5 minutes to balance freshness and API load.
        """
        cloud_wrapper = self.api_client.cloud_client
        
        # Use SDK's batch processing method
        await cloud_wrapper.async_fetch_and_process_device_details(
            devices=devices,
            cache=self._device_detail_cache,
            cache_ttl=self._device_detail_cache_ttl,
            max_concurrent=5,
        )

    def _merge_device_states(self, devices: dict[str, HeimanDevice]) -> None:
        """Merge old device states with new device data."""
        old_devices = self.data.devices.copy()
        self.data.devices = devices

        # Use the SDK's merge_from method to handle property merging
        for device_id, new_device in devices.items():
            if device_id in old_devices:
                new_device.merge_from(old_devices[device_id])

    def get_device(self, device_id: str) -> HeimanDevice | None:
        """Get device by ID.

        Args:
            device_id: Device ID to retrieve

        Returns:
            HeimanDevice object or None if not found
        """
        return self.data.devices.get(device_id)

    def get_all_devices(self) -> list[HeimanDevice]:
        """Get all devices.

        Returns:
            List of all HeimanDevice objects
        """
        return list(self.data.devices.values())

    def get_devices_by_type(self, device_type: str) -> list[HeimanDevice]:
        """Get devices by type.

        Args:
            device_type: Device type to filter by

        Returns:
            List of matching HeimanDevice objects
        """
        return [
            device
            for device in self.data.devices.values()
            if device.device_type == device_type
        ]

    async def async_init_mqtt_client(self) -> None:
        """Initialize MQTT client for real-time updates."""
        if self.mqtt_client:
            return

        try:
            # Get authentication data from config entry or OAuth2 session
            access_token = None
            user_id = self.config_entry.data.get(CONF_USER_ID)

            # Try to get from config entry token data first
            token_data = self.config_entry.data.get(CONF_TOKEN)
            if token_data and isinstance(token_data, dict):
                access_token = token_data.get("access_token")

            # Fallback: try to get from OAuth2 session if not in config
            if not access_token and self.oauth_session:
                try:
                    await self.oauth_session.async_ensure_token_valid()
                    # After ensuring token is valid, get it from session.token
                    if self.oauth_session.token:
                        access_token = self.oauth_session.token.get("access_token")
                    else:
                        _LOGGER.debug("OAuth2 session token is None after validation")
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Failed to get access_token from session: %s", err)

            if not access_token:
                _LOGGER.warning(
                    "Cannot initialize MQTT: access_token not available from any source"
                )
                return

            if not user_id:
                _LOGGER.warning("Cannot initialize MQTT: user_id not available")
                return

            # Get user display name using SDK method
            user_display_name = None
            if self.data.user_info:
                user_display_name = self.data.user_info.get_display_name()

            # Get cloud client reference for child device detection
            cloud_client = None
            try:
                # Access the underlying cloud client from the wrapper
                if hasattr(self.api_client, "_wrapper") and self.api_client._wrapper:  # noqa: SLF001
                    cloud_client = self.api_client._wrapper.cloud_client  # noqa: SLF001
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to get cloud_client reference: %s", err)

            # Get devices dictionary for child device detection
            devices_dict = dict(self.data.devices) if self.data.devices else {}

            # Create and connect MQTT client
            self.mqtt_client = HeimanMqttClient(
                hass=self.hass,
                access_token=access_token,
                user_id=user_id,
                user_display_name=user_display_name,
                cloud_client=cloud_client,
                devices=devices_dict,  # Pass devices dictionary
            )

            await self.mqtt_client.connect()

            # Register callback for device property updates
            self.mqtt_client.register_device_callback(self._on_device_property_update)

        except HeimanMQTTError as err:
            _LOGGER.error("Failed to initialize MQTT client: %s", err)
            # Disconnect any partially connected client before clearing reference
            if self.mqtt_client is not None:
                with contextlib.suppress(Exception):
                    await _async_call_cleanup_method(
                        self.mqtt_client,
                        (
                            "async_disconnect",
                            "disconnect",
                            "async_close",
                            "close",
                        ),
                    )
            # Clear mqtt_client so future calls can retry
            self.mqtt_client = None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Unexpected error initializing MQTT client: %s", err)
            # Disconnect any partially connected client before clearing reference
            if self.mqtt_client is not None:
                with contextlib.suppress(Exception):
                    await _async_call_cleanup_method(
                        self.mqtt_client,
                        (
                            "async_disconnect",
                            "disconnect",
                            "async_close",
                            "close",
                        ),
                    )
            # Clear mqtt_client so future calls can retry
            self.mqtt_client = None

    def _on_device_property_update(
        self, device_id: str, properties: dict[str, Any]
    ) -> None:
        """Handle device property update from MQTT.

        Args:
            device_id: Device ID that sent the update
            properties: Dictionary of property name to value
        """
        # Find device in coordinator data
        device = self.data.devices.get(device_id)
        if not device:
            return

        # Update device properties
        for prop_name, prop_value in properties.items():
            if prop_name in device.properties:
                device.properties[prop_name].value = prop_value
            else:
                # Add new property if it doesn't exist
                # Infer entity type from property value using SDK method
                entity_type = DeviceProperty.infer_entity_type(prop_value)
                if entity_type is not None:
                    device.properties[prop_name] = DeviceProperty(
                        identifier=prop_name,
                        name=prop_name,
                        value=prop_value,
                        readable=True,
                        entity=entity_type,
                    )

        # Schedule entity update if coordinator is set up
        # IMPORTANT: Must be called from the event loop thread for thread safety
        if hasattr(self, "async_set_updated_data") and self.hass:
            # Use hass.add_job to schedule the update in the event loop
            # Pass the coroutine function and data as arguments
            self.hass.add_job(self.async_set_updated_data, self.data)

    async def async_read_device_properties(self, device_id: str) -> None:
        """Read properties from a specific device via MQTT.

        Args:
            device_id: Device ID to read properties from
        """
        if not self.mqtt_client:
            _LOGGER.warning("MQTT client not initialized, cannot read properties")
            return

        device = self.data.devices.get(device_id)
        if not device:
            _LOGGER.warning("Device %s not found in coordinator", device_id)
            return

        try:
            # Read all properties (empty list means read all)
            properties = await self.mqtt_client.async_read_properties(
                device_id=device_id,
                product_id=device.product_id,
                property_identifiers=None,  # Read all available properties
            )

            # Update device properties in coordinator data
            if properties:
                for prop_name, prop_value in properties.items():
                    if prop_name in device.properties:
                        device.properties[prop_name].value = prop_value
                    else:
                        # Add new property if it doesn't exist
                        # Infer entity type from property value using SDK method
                        entity_type = DeviceProperty.infer_entity_type(prop_value)
                        if entity_type is not None:
                            device.properties[prop_name] = DeviceProperty(
                                identifier=prop_name,
                                name=prop_name,
                                value=prop_value,
                                readable=True,
                                entity=entity_type,
                            )

                # Trigger entity update
                # IMPORTANT: Must be called from the event loop thread for thread safety
                if hasattr(self, "async_set_updated_data") and self.hass:
                    # Use hass.add_job to schedule the update in the event loop
                    # Pass the coroutine function and data as arguments
                    self.hass.add_job(self.async_set_updated_data, self.data)
            else:
                _LOGGER.warning("No properties returned from device %s", device_id)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to read properties from device %s: %s", device_id, err
            )

    def get_online_devices(self) -> list[HeimanDevice]:
        """Get all online devices.

        Returns:
            List of online HeimanDevice objects
        """
        return [
            device for device in self.data.devices.values() if device.online is True
        ]

    def get_device_property(self, device_id: str, property_name: str) -> Any | None:
        """Get device property value from cache.

        Args:
            device_id: Device ID
            property_name: Property name

        Returns:
            Property value if found, None otherwise
        """
        device = self.data.devices.get(device_id)
        if not device:
            return None

        prop = device.properties.get(property_name)
        if not prop:
            return None

        return prop.value
