"""API client for Hisense ConnectLife - Home Assistant Adapter."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from connectlife_cloud import (
    ConnectLifeCloudClient,
    DeviceInfo,
    DeviceParserFactory,
)
from connectlife_cloud.devices.base import BaseDeviceParser, DeviceAttribute
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CLIENT_ID, CLIENT_SECRET, DOMAIN
from .models import HisenseApiError
from .oauth2 import OAuth2Session
from .websocket import HisenseWebSocket

_LOGGER = logging.getLogger(__name__)


class HisenseApiClient:
    """Home Assistant adapter for ConnectLife Cloud API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize API client adapter."""
        self.hass = hass
        self.oauth_session = oauth_session
        
        # Initialize the ConnectLife Cloud client
        self.client = ConnectLifeCloudClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            session=oauth_session.session,
        )
        
        self._devices: dict[str, DeviceInfo] = {}
        self._status_callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._websocket: HisenseWebSocket | None = None

    @property
    async def async_get_devices(self) -> dict[str, DeviceInfo]:
        """Get list of devices with their current status.
        
        Returns:
            Dictionary mapping device_id to DeviceInfo
        """
        _LOGGER.debug("Fetching device list with status")
        
        try:
            # Get access token
            access_token = await self.oauth_session.async_get_access_token()
            
            # Use the cloud client to get devices with parsers
            devices_with_parsers = await self.client.get_devices_with_parsers(access_token)
            
            # Update power consumption for devices that support it
            for device_id, (device, parser) in devices_with_parsers.items():
                self._devices[device_id] = device
                
                # Check if device has power consumption attribute
                if "f_power_consumption" in parser.attributes:
                    try:
                        await self._update_power_consumption(device)
                    except Exception as power_err:
                        _LOGGER.warning(
                            "Failed to update power consumption for device %s: %s",
                            device_id,
                            power_err
                        )
                
                # Update failed data (self-check)
                try:
                    await self._update_self_check_data(device, access_token)
                except Exception as self_check_err:
                    _LOGGER.warning(
                        "Failed to update self-check data for device %s: %s",
                        device_id,
                        self_check_err
                    )
            
            return self._devices
            
        except Exception as err:
            _LOGGER.error("Failed to fetch devices: %s", err)
            raise HisenseApiError(f"Error communicating with API: {err}")

    async def _update_power_consumption(self, device: DeviceInfo) -> None:
        """Update power consumption for a device.
        
        Args:
            device: Device to update
        """
        access_token = await self.oauth_session.async_get_access_token()
        current_date = datetime.now().date().isoformat()
        
        power_response = await self.client.get_hour_power(
            current_date, device.puid, access_token
        )
        power_data = power_response.get("status", {})
        
        current_time = datetime.now()
        previous_hour = (current_time - timedelta(hours=1)).hour
        previous_hour_str = str(previous_hour)
        value = power_data.get(previous_hour_str)
        
    if value is not None:
                device.status["f_power_consumption"] = value
    _LOGGER.debug(
        "Updated power consumption for device %s: %s",
        device.device_id,
        value
    )

    async def _update_self_check_data(
        self, device: DeviceInfo, access_token: str
    ) -> None:
        """Update self-check data for a device.
        
        Args:
            device: Device to update
            access_token: OAuth2 access token
        """
        data = await self.client.get_self_check("1", device.puid, access_token)
        failed_data = data.get("status", {}).get("selfCheckFailedList")

        if failed_data:
            failed_list = [item.get("statusKey") for item in failed_data]
            device.failed_data = failed_list
            _LOGGER.debug(
        "Updated self-check data for device %s: %s failures found",
        device.device_id,
        len(failed_list)
    )

    async def async_setup_websocket(self) -> None:
        """Set up WebSocket connection."""
        if self._websocket is None:
            self._websocket = HisenseWebSocket(
                self.hass,
                self,
                self._handle_ws_message,
            )
            await self._websocket.async_connect()

    async def async_cleanup(self) -> None:
        """Clean up resources."""
        if self._websocket is not None:
            await self._websocket.async_disconnect()
            self._websocket = None
        
        await self.client.close()

    def register_status_callback(
        self,
        device_id: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a callback for device status updates."""
        self._status_callbacks[device_id] = callback

    def _handle_ws_message(self, data: dict[str, Any]) -> None:
        """Handle WebSocket message.
        
        Args:
            data: WebSocket message data
        """
        device_id = data.get("deviceId")
        if device_id and device_id in self._status_callbacks:
            properties = data.get("properties", {})
            self._status_callbacks[device_id](properties)

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get device status from cached device list.
        
        Args:
            device_id: Device ID
            
        Returns:
            Parsed device status
        """
        device = self._devices.get(device_id)
        if not device:
            # If device not in cache, refresh the device list once
            devices = await self.async_get_devices
            device = devices.get(device_id)
            if not device:
                raise HisenseApiError(f"Device not found: {device_id}")
        
        # Use the cloud client to parse device status
        return self.client.parse_device_status(device_id, device.status)

    async def async_control_device(
        self,
        puid: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Control device by setting properties.
        
        Args:
            puid: Device ID to control
            properties: Properties to set, e.g. {"power": True, "mode": "cool"}
            
        Returns:
            Dict containing the response status and any returned properties
            
        Raises:
            HisenseApiError: If the API request fails
        """
        _LOGGER.debug("Controlling device %s with properties: %s", puid, properties)
        
        try:
            access_token = await self.oauth_session.async_get_access_token()
            response = await self.client.control_device(puid, properties, access_token)
            
            if response.get("success"):
                return {
                    "success": True,
                    "status": response.get("status", {}),
                }
            else:
                raise HisenseApiError("Control failed")
                
        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

    async def _api_request(
            self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Make an API request (delegated to cloud client).
        
        This method is kept for backward compatibility with WebSocket.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            headers: Request headers
            
        Returns:
            API response
        """
        access_token = await self.oauth_session.async_get_access_token()
        return await self.client._api_request(
            method=method,
            endpoint=endpoint,
            data=data,
            headers=headers,
            access_token=access_token,
        )

    def get_parser(self, device_id: str) -> BaseDeviceParser | None:
        """Get parser for a device.
        
        Args:
            device_id: Device ID
            
        Returns:
            Device parser or None
        """
        return self.client.get_parser(device_id)


    @property
    def parsers(self) -> dict[str, BaseDeviceParser]:
        """Get device parsers dictionary.
        
        This property provides backward compatibility for diagnostics and tests.
        
        Returns:
            Dictionary mapping device_id to parser
        """
        return self.client._parsers

    @property
    def static_data(self) -> dict[str, Any]:
        """Get static data dictionary.
        
        This property provides backward compatibility for diagnostics and tests.
        
        Returns:
            Dictionary mapping device_id to static data
        """
        return self.client._static_data
