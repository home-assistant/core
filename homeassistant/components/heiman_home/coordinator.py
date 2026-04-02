"""Data update coordinator for Heiman integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeimanApiClient
from .const import CONF_HOME_ID, CONF_USER_ID

_LOGGER = logging.getLogger(__name__)


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
            name="Heiman Home",
            update_interval=None,  # Disabled automatic refresh
        )

        self.api_client = api_client
        self.config_entry = config_entry
        self.device_management = device_management
        self.data = HeimanData()
        self.mqtt_client: HeimanMqttClient | None = None
        self.oauth_session = oauth_session

    async def _async_update_data(self) -> HeimanData:
        """Fetch data from Heiman API.

        Returns:
            HeimanData object with updated information

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If data fetch fails
        """
        home_id = self.config_entry.data.get(CONF_HOME_ID)
        if not home_id:
            raise UpdateFailed("Home ID not found in config entry")

        try:
            await self._async_maybe_fetch_user_info()
            await self._async_maybe_fetch_home_info(home_id)

            devices = await self._async_fetch_devices(home_id)
            old_devices = self.data.devices.copy()
            self.data.devices = devices
            self._merge_old_device_state(old_devices, devices)

            self.data.last_update = datetime.now()
            self.data.errors.clear()
        except ConfigEntryAuthFailed:
            _LOGGER.error("Authentication failed during data update")
            raise
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Error fetching Heiman data: {err}") from err
        else:
            return self.data

    async def _async_maybe_fetch_user_info(self) -> None:
        if self.data.user_info is not None:
            return

        try:
            user_info = await self.api_client.async_get_user_info()
        except ConfigEntryAuthFailed:
            raise
        except HeimanConnectionError as err:
            _LOGGER.warning("Failed to fetch user info: %s", err)
            self.data.errors["user_info"] = str(err)
        else:
            self.data.user_info = user_info
            _LOGGER.debug("Fetched user info: %s", user_info.email)

    async def _async_maybe_fetch_home_info(self, home_id: str) -> None:
        if self.data.home_info is not None:
            return

        try:
            homes = await self.api_client.async_get_homes()
        except ConfigEntryAuthFailed:
            raise
        except HeimanConnectionError as err:
            _LOGGER.warning("Failed to fetch home info: %s", err)
            self.data.errors["home_info"] = str(err)
            return

        if not homes:
            return

        self.data.home_info = next((h for h in homes if h.home_id == home_id), homes[0])
        _LOGGER.debug("Fetched home info: %s", self.data.home_info.home_name)

    async def _async_fetch_devices(self, home_id: str) -> dict[str, HeimanDevice]:
        try:
            devices_dict = await self.api_client.async_get_devices(home_id=home_id)
        except ConfigEntryAuthFailed:
            raise
        except HeimanConnectionError as err:
            _LOGGER.error("Failed to fetch devices: %s", err)
            self.data.errors["devices"] = str(err)
            if not self.data.devices:
                raise UpdateFailed(f"Failed to fetch devices: {err}") from err
            return self.data.devices

        devices = self._apply_device_filter(devices_dict)
        self._extract_firmware_versions(devices)
        await self._async_update_device_details(devices)

        _LOGGER.debug("Fetched %d devices", len(devices))
        return devices

    def _apply_device_filter(
        self, devices_dict: dict[str, HeimanDevice]
    ) -> dict[str, HeimanDevice]:
        if not self.device_management:
            return devices_dict

        devices_list = list(devices_dict.values())
        filtered_devices_list = (
            self.device_management.filter_manager.get_filtered_devices(devices_list)
        )
        devices = {device.device_id: device for device in filtered_devices_list}
        _LOGGER.info(
            "Device filter applied: %d/%d devices included",
            len(devices),
            len(devices_dict),
        )
        return devices

    def _extract_firmware_versions(self, devices: dict[str, HeimanDevice]) -> None:
        for device_id, device in devices.items():
            _LOGGER.debug(
                "Device %s attributes: raw_data=%s firmware_info=%s firmware_version=%s",
                device_id,
                hasattr(device, "raw_data"),
                hasattr(device, "firmware_info"),
                getattr(device, "firmware_version", "NOT_SET"),
            )

            if hasattr(device, "raw_data") and device.raw_data:
                firmware_info = device.raw_data.get("firmwareInfo", {})
                if isinstance(firmware_info, dict) and "version" in firmware_info:
                    device.firmware_version = firmware_info.get("version")
                    _LOGGER.info(
                        "Extracted firmware version %s for device %s from raw_data",
                        device.firmware_version,
                        device_id,
                    )

            if hasattr(device, "firmware_info") and device.firmware_info:
                firmware_info = device.firmware_info
                if isinstance(firmware_info, dict) and "version" in firmware_info:
                    device.firmware_version = firmware_info.get("version")
                    _LOGGER.debug(
                        "Extracted firmware version %s for device %s from firmware_info",
                        device.firmware_version,
                        device_id,
                    )

    async def _async_update_device_details(
        self, devices: dict[str, HeimanDevice]
    ) -> None:
        _LOGGER.debug("Fetching device details for %d devices", len(devices))

        to_level = self._convert_dbm_to_level
        for device_id, device in devices.items():
            try:
                device_detail = await self.api_client.async_get_device_detail(device_id)
            except HeimanConnectionError as err:
                _LOGGER.debug("Failed to get detail for device %s: %s", device_id, err)
                continue

            if not device_detail:
                continue

            if not device.firmware_version:
                firmware_info = device_detail.get("firmwareInfo", {})
                if isinstance(firmware_info, dict) and "version" in firmware_info:
                    device.firmware_version = firmware_info.get("version")

            metadata_str = device_detail.get("deriveMetadata")
            if metadata_str:
                self._apply_derive_metadata(
                    device_id=device_id,
                    device=device,
                    metadata_str=metadata_str,
                    to_level=to_level,
                )

    def _apply_derive_metadata(
        self,
        device_id: str,
        device: HeimanDevice,
        metadata_str: str,
        to_level,
    ) -> None:
        try:
            metadata_list = json.loads(metadata_str)
        except ValueError, TypeError:
            _LOGGER.exception("Failed to parse deriveMetadata for %s", device_id)
            return

        if not isinstance(metadata_list, list):
            return

        for prop_item in metadata_list:
            prop_id = prop_item.get("property", "") or prop_item.get("id", "")
            prop_value = prop_item.get("value")

            if not prop_id or prop_value is None:
                continue

            if prop_id == "DeviceINFO" and isinstance(prop_value, dict):
                self._apply_device_info(device_id, device, prop_value, to_level)
                continue

            if prop_id not in device.properties:
                continue

            device.properties[prop_id].value = prop_value

    def _apply_device_info(
        self,
        device_id: str,
        device: HeimanDevice,
        device_info: dict[str, Any],
        to_level,
    ) -> None:
        mac_value = device_info.get("MAC")
        if mac_value and "DeviceINFO_MAC" in device.properties:
            device.properties["DeviceINFO_MAC"].value = mac_value

        dbm_value = device_info.get("DBM")
        if dbm_value is not None and "DeviceINFO_DBM" in device.properties:
            device.properties["DeviceINFO_DBM"].value = dbm_value

        if dbm_value is not None and "DeviceINFO_DBM_Level" in device.properties:
            device.properties["DeviceINFO_DBM_Level"].value = to_level(dbm_value)

        ip_value = device_info.get("IP")
        if ip_value and "DeviceINFO_IP" in device.properties:
            device.properties["DeviceINFO_IP"].value = ip_value

    @staticmethod
    def _merge_old_device_state(
        old_devices: dict[str, HeimanDevice],
        new_devices: dict[str, HeimanDevice],
    ) -> None:
        for device_id, new_device in new_devices.items():
            old_device = old_devices.get(device_id)
            if not old_device:
                continue

            for prop_id, old_prop in old_device.properties.items():
                if prop_id in new_device.properties and old_prop.value is not None:
                    new_device.properties[prop_id].value = old_prop.value

            if not new_device.online and old_device.online:
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
            Signal level string: "Strong", "Medium", "Weak", or "Very Weak"
        """
        # DBM values are typically negative numbers
        # Closer to 0 = stronger signal
        if dbm_value >= -50:
            return "Strong"
        if dbm_value >= -65:
            return "Medium"
        if dbm_value >= -75:
            return "Weak"
        return "Very Weak"

    async def async_init_mqtt_client(self) -> None:
        """Initialize MQTT client for real-time updates."""
        if self.mqtt_client:
            _LOGGER.debug("MQTT client already initialized")
            return

        try:
            user_id = self.config_entry.data.get(CONF_USER_ID)

            # Try to get from config first
            access_token = self.config_entry.data.get("access_token")

            # Fallback: try to get from OAuth2 session if not in config
            if not access_token and self.oauth_session:
                try:
                    token_data = await self.oauth_session.async_ensure_token_valid()
                except (OAuth2TokenRequestError, OAuth2TokenRequestReauthError) as err:
                    _LOGGER.warning("Failed to get access_token from session: %s", err)
                else:
                    if token_data:
                        access_token = token_data.get("access_token")
                    else:
                        _LOGGER.warning("async_ensure_token_valid() returned None")

            # Final fallback: get token from api_client
            if not access_token:
                access_token = self.api_client.get_access_token()

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
            if self.data.user_info:
                user_display_name = getattr(self.data.user_info, "nick_name", None)
                if not user_display_name:
                    user_display_name = getattr(self.data.user_info, "email", None)

            # Get cloud client reference for child device detection
            cloud_client = self.api_client.cloud_client

            # Get devices dictionary for child device detection
            devices_dict = dict(self.data.devices) if self.data.devices else {}
            _LOGGER.debug(
                "Passing %d devices to MQTT client for child device detection",
                len(devices_dict),
            )

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

            _LOGGER.info("MQTT client initialized successfully")

        except HeimanMQTTError as err:
            _LOGGER.error("Failed to initialize MQTT client: %s", err)
        except (OSError, RuntimeError, ValueError) as err:
            _LOGGER.error("Unexpected error initializing MQTT client: %s", err)

    def _on_device_property_update(
        self, device_id: str, properties: dict[str, Any]
    ) -> None:
        """Handle device property update from MQTT.

        Args:
            device_id: Device ID that sent the update
            properties: Dictionary of property name to value
        """
        _LOGGER.debug(
            "Received property update for device %s: %s", device_id, properties
        )

        # Find device in coordinator data
        device = self.data.devices.get(device_id)
        if not device:
            _LOGGER.debug(
                "Device %s not found in coordinator, ignoring update", device_id
            )
            return

        # Update device properties
        for prop_name, prop_value in properties.items():
            if prop_name in device.properties:
                old_value = device.properties[prop_name].value
                device.properties[prop_name].value = prop_value
                _LOGGER.debug(
                    "Updated property %s for device %s: %s -> %s",
                    prop_name,
                    device_id,
                    old_value,
                    prop_value,
                )
            else:
                # Add new property if it doesn't exist
                device.properties[prop_name] = DeviceProperty(
                    identifier=prop_name,
                    name=prop_name,
                    value=prop_value,
                )
                _LOGGER.debug(
                    "Added new property %s for device %s", prop_name, device_id
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
            _LOGGER.info(
                "Reading properties from device %s (%s)", device.device_name, device_id
            )

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
                        old_value = device.properties[prop_name].value
                        device.properties[prop_name].value = prop_value
                        _LOGGER.debug(
                            "Updated property %s for device %s: %s -> %s",
                            prop_name,
                            device_id,
                            old_value,
                            prop_value,
                        )
                    else:
                        # Add new property if it doesn't exist
                        device.properties[prop_name] = DeviceProperty(
                            identifier=prop_name,
                            name=prop_name,
                            value=prop_value,
                        )
                        _LOGGER.debug(
                            "Added new property %s for device %s", prop_name, device_id
                        )

                # Trigger entity update
                # IMPORTANT: Must be called from the event loop thread for thread safety
                if hasattr(self, "async_set_updated_data") and self.hass:
                    # Use hass.add_job to schedule the update in the event loop
                    # Pass the coroutine function and data as arguments
                    self.hass.add_job(self.async_set_updated_data, self.data)

                _LOGGER.info(
                    "Successfully read %d properties from device %s",
                    len(properties),
                    device_id,
                )
            else:
                _LOGGER.warning("No properties returned from device %s", device_id)

        except (HeimanMQTTError, OSError, RuntimeError) as err:
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
