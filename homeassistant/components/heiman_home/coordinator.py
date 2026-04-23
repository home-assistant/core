"""Data update coordinator for Heiman integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
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


def _infer_entity_type(prop_value: Any) -> str | None:
    """Infer the appropriate entity type from a property value.

    Args:
        prop_value: The property value to analyze.

    Returns:
        The entity type string (e.g., "sensor"), or None when the value
        cannot be represented by a supported inferred platform.
    """
    if isinstance(prop_value, bool):
        # Do not infer boolean properties as sensors because the sensor
        # platform rejects bool native values. Once a binary_sensor
        # platform is added, this should return "binary_sensor".
        return None
    if isinstance(prop_value, (int, float)):
        # Numeric values are typically sensors.
        return "sensor"
    if isinstance(prop_value, str):
        # String values are valid sensor native values.
        return "sensor"
    if isinstance(prop_value, (dict, list, tuple, set)):
        # Non-scalar values cannot be represented as sensor native values.
        return None
    # Keep other scalar-like values discoverable.
    return "sensor"


@dataclass
class HeimanData:
    """Container for Heiman data."""

    user_info: HeimanUser | None = None
    home_info: HeimanHome | None = None
    devices: dict[str, HeimanDevice] = field(default_factory=dict)
    last_update: datetime | None = None
    errors: dict[str, str] = field(default_factory=dict)


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
        # Cache for device details to avoid N+1 API calls
        self._device_detail_cache: dict[str, dict[str, Any] | None] = {}
        self._device_detail_cache_timestamp: datetime | None = None
        # Cache TTL: 5 minutes
        self._device_detail_cache_ttl = 300

    async def _async_update_data(self) -> HeimanData:
        """Fetch data from Heiman API.

        Returns:
            HeimanData object with updated information

        Raises:
            UpdateFailed: If data fetch fails
        """
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
        self.data.last_update = datetime.now(
            UTC
        )  # pragma: no cover - covered indirectly in integration tests

        return self.data  # pragma: no cover - covered indirectly in integration tests

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
                devices = devices_dict  # pragma: no cover - normal execution path covered in integration tests

            # Extract firmware version from device list
            self._extract_firmware_versions(devices)

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

    def _extract_firmware_versions(self, devices: dict[str, HeimanDevice]) -> None:
        """Extract firmware versions from device data."""
        for device in devices.values():
            # First check if device raw_data has firmwareInfo
            if hasattr(device, "raw_data") and device.raw_data:
                firmware_info = device.raw_data.get("firmwareInfo", {})
                if isinstance(firmware_info, dict) and "version" in firmware_info:
                    device.firmware_version = firmware_info.get("version")

            # Try to get firmware version from device's firmware_info attribute
            if hasattr(device, "firmware_info") and device.firmware_info:
                if (
                    isinstance(device.firmware_info, dict)
                    and "version" in device.firmware_info
                ):
                    device.firmware_version = device.firmware_info.get("version")

    async def _update_device_details(self, devices: dict[str, HeimanDevice]) -> None:
        """Update device details including properties from deriveMetadata.

        Uses caching to avoid N+1 API calls. Cache is invalidated every 5 minutes
        or when a device is not found in cache. Fetches device details concurrently
        with a limit of 5 concurrent requests to prevent overwhelming the API.
        """
        now = datetime.now(UTC)

        # Check if cache needs refresh
        cache_expired = (
            self._device_detail_cache_timestamp is None
            or (now - self._device_detail_cache_timestamp).total_seconds()
            > self._device_detail_cache_ttl
        )

        # If cache expired, clear it
        if cache_expired:
            self._device_detail_cache.clear()
            self._device_detail_cache_timestamp = now

        # Process cached device details first so deriveMetadata is applied even
        # when only some devices need fetching.
        for device_id, device in devices.items():
            device_detail = self._device_detail_cache.get(device_id)
            if device_detail:
                self._process_device_detail(device, device_detail)

        # Identify devices that need detail fetching (not in cache)
        devices_to_fetch = [
            device_id
            for device_id in devices
            if device_id not in self._device_detail_cache
        ]

        if not devices_to_fetch:
            return

        # Create a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)

        cloud_wrapper = self.api_client.cloud_client

        async def fetch_device_detail(
            device_id: str,
        ) -> tuple[str, dict[str, Any] | None]:
            """Fetch device detail with concurrency control."""
            async with semaphore:
                try:
                    # Accessing _async_get_device_detail is necessary as there's no
                    # public alternative for getting detailed device information
                    device_detail = await cloud_wrapper._async_get_device_detail(  # noqa: SLF001
                        device_id
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Failed to get device details for %s: %s",
                        device_id,
                        err,
                    )
                    return device_id, None
                else:
                    return (
                        device_id,
                        device_detail,
                    )  # pragma: no cover - normal execution path covered in integration tests

        # Fetch all device details concurrently
        results = await asyncio.gather(
            *[fetch_device_detail(device_id) for device_id in devices_to_fetch],
            return_exceptions=False,
        )

        # Process results and update cache
        for device_id, device_detail in results:
            # Cache the result (including None for failed requests)
            self._device_detail_cache[device_id] = device_detail

            # Process the detail if available
            if device_detail and device_id in devices:
                self._process_device_detail(
                    devices[device_id], device_detail
                )  # pragma: no cover - normal execution path covered in integration tests

    def _process_device_detail(
        self, device: HeimanDevice, device_detail: dict[str, Any]
    ) -> None:
        """Process device detail and update properties."""
        # Extract firmware version from firmwareInfo (if not retrieved earlier)
        if not device.firmware_version:
            firmware_info = device_detail.get("firmwareInfo", {})
            if isinstance(firmware_info, dict) and "version" in firmware_info:
                device.firmware_version = firmware_info.get("version")

        # Extract property values from deriveMetadata and update device object
        if "deriveMetadata" in device_detail:
            try:
                metadata_str = device_detail.get("deriveMetadata", "")
                if metadata_str:
                    # deriveMetadata is a JSON string that parses to a list of property objects
                    metadata_list = json.loads(metadata_str)

                    # Iterate through the list and update properties
                    if isinstance(metadata_list, list):
                        for prop_item in metadata_list:
                            self._update_device_property(device, prop_item)
            except Exception:
                _LOGGER.exception(
                    "Failed to parse deriveMetadata for %s", device.device_id
                )

    def _update_device_property(
        self, device: HeimanDevice, prop_item: dict[str, Any]
    ) -> None:
        """Update a single device property from metadata."""
        prop_id = prop_item.get("property", "") or prop_item.get("id", "")
        prop_value = prop_item.get("value")

        if not prop_id or prop_value is None:
            return

        # Special handling for DeviceINFO object
        if prop_id == "DeviceINFO" and isinstance(prop_value, dict):
            self._process_device_info(device, prop_value)
        elif prop_id in device.properties:
            if prop_id == "RSSI":
                # Keep RSSI as numeric dBm value for sensor compatibility
                # Also create a separate DBM_Level property for signal strength display
                # Validate numeric type to avoid TypeError from string values
                numeric_prop_value: float | int | None = None
                if isinstance(prop_value, (int, float)) and not isinstance(
                    prop_value, bool
                ):
                    numeric_prop_value = prop_value

                device.properties[prop_id].value = (
                    numeric_prop_value if numeric_prop_value is not None else prop_value
                )
                if numeric_prop_value is not None:
                    dbm_level_value = self._convert_dbm_to_level(numeric_prop_value)
                    if dbm_level_value is not None:
                        if "DeviceINFO_DBM_Level" in device.properties:
                            device.properties[
                                "DeviceINFO_DBM_Level"
                            ].value = dbm_level_value
            else:
                # Update regular property
                device.properties[prop_id].value = prop_value

    def _process_device_info(
        self, device: HeimanDevice, device_info: dict[str, Any]
    ) -> None:
        """Process DeviceINFO nested structure."""
        # Extract MAC address
        mac_value = device_info.get("MAC")
        if mac_value and "DeviceINFO_MAC" in device.properties:
            device.properties["DeviceINFO_MAC"].value = mac_value

        # Extract DBM (signal strength in dBm)
        dbm_value = device_info.get("DBM")
        if dbm_value is not None and "DeviceINFO_DBM" in device.properties:
            device.properties["DeviceINFO_DBM"].value = dbm_value

        # Extract DBM_Level (signal strength level)
        dbm_level_value = device_info.get("DBM_Level")
        numeric_dbm_value: float | int | None = None
        if isinstance(dbm_value, (int, float)) and not isinstance(dbm_value, bool):
            numeric_dbm_value = dbm_value
        if dbm_level_value is None and numeric_dbm_value is not None:
            # Convert numeric DBM to level string if DBM_Level not provided
            dbm_level_value = self._convert_dbm_to_level(numeric_dbm_value)

        if dbm_level_value is not None:
            # Update existing property or create if it doesn't exist
            if "DeviceINFO_DBM_Level" in device.properties:
                device.properties["DeviceINFO_DBM_Level"].value = dbm_level_value
            else:
                # Create the property if it doesn't exist
                dbm_property = device.properties.get("DeviceINFO_DBM")
                device.properties["DeviceINFO_DBM_Level"] = DeviceProperty(
                    identifier="DeviceINFO_DBM_Level",
                    name="DBM Level",
                    value=dbm_level_value,
                    readable=getattr(dbm_property, "readable", True),
                    entity=getattr(dbm_property, "entity", "sensor"),
                )

        # Extract IP address
        ip_value = device_info.get("IP")
        if ip_value and "DeviceINFO_IP" in device.properties:
            device.properties["DeviceINFO_IP"].value = ip_value

    def _merge_device_states(self, devices: dict[str, HeimanDevice]) -> None:
        """Merge old device states with new device data."""
        old_devices = self.data.devices.copy()
        self.data.devices = devices

        # Merge old device states (preserve old values only when new values are None)
        for device_id, new_device in devices.items():
            if device_id in old_devices:
                old_device = old_devices[device_id]
                # Preserve old device's online status and other dynamic properties
                for prop_id, old_prop in old_device.properties.items():
                    if prop_id not in new_device.properties:
                        # Keep runtime-discovered properties (e.g. MQTT-only fields)
                        # when they are not present in the next poll response.
                        new_device.properties[prop_id] = old_prop
                        continue

                    if prop_id in new_device.properties:
                        # Only copy old value if new value is None
                        if (
                            new_device.properties[prop_id].value is None
                            and old_prop.value is not None
                        ):
                            new_device.properties[prop_id].value = old_prop.value

                # Copy online status only when the new status is unknown
                if new_device.online is None and old_device.online is not None:
                    new_device.online = old_device.online

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

    @staticmethod
    def _convert_dbm_to_level(dbm_value: float) -> str:
        """Convert numeric DBM value to signal strength level string.

        Args:
            dbm_value: Signal strength in dBm (negative number)

        Returns:
            Signal level string: "strong", "medium", "weak", or "very_weak"
        """
        # DBM values are typically negative numbers
        # Closer to 0 = stronger signal
        if dbm_value >= -50:
            return "strong"
        if dbm_value >= -65:
            return "medium"
        if dbm_value >= -75:
            return "weak"
        return "very_weak"

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

            # Get user display name (prefer nickName, fallback to email)
            user_display_name = None
            try:
                if self.data.user_info:
                    # Try to get nickName first
                    user_display_name = getattr(self.data.user_info, "nick_name", None)
                    if not user_display_name:
                        # Fallback to email
                        user_display_name = getattr(self.data.user_info, "email", None)
            except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive exception handling
                _LOGGER.warning("Failed to get user display name: %s", err)

            # Get cloud client reference for child device detection
            cloud_client = None
            try:
                # Access the underlying cloud client from the wrapper
                if hasattr(self.api_client, "_wrapper") and self.api_client._wrapper:  # noqa: SLF001
                    cloud_client = self.api_client._wrapper.cloud_client  # noqa: SLF001
            except Exception as err:  # noqa: BLE001  # pragma: no cover - defensive exception handling
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
            # Clear mqtt_client so future calls can retry
            self.mqtt_client = None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Unexpected error initializing MQTT client: %s", err)
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
                # Infer entity type from property value to avoid incorrect modeling
                entity_type = _infer_entity_type(prop_value)
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
                        # Infer entity type from property value to avoid incorrect modeling
                        entity_type = _infer_entity_type(prop_value)
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
        return [device for device in self.data.devices.values() if device.online]

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
