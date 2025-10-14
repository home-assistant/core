"""Data update coordinator for Hisense AC Plugin."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HisenseApiClient, DeviceInfo
from .const import UPDATE_INTERVAL
from .websocket import HisenseWebSocket

_LOGGER = logging.getLogger(__name__)

class HisenseACPluginDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: HisenseApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="hisense_connectlife",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api_client = api_client
        self.config_entry = config_entry
        self._devices: dict[str, DeviceInfo] = {}
        self._websocket: HisenseWebSocket | None = None
        self._websocket_connected = False

    async def async_setup(self) -> bool:
        """Set up the coordinator."""
        try:
            # Get initial device list
            devices = await self.api_client.async_get_devices
            if not devices:
                _LOGGER.error("No devices found during setup")
                return False
                
            _LOGGER.debug("Initial device list: %s", devices)
            self._devices = devices
            self.data = devices  # Set initial data
            
            # Set up WebSocket connection
            self._websocket = HisenseWebSocket(
                self.hass,
                self.api_client,
                self._handle_ws_message
            )
            await self._websocket.async_connect()
            self._websocket_connected = True
            _LOGGER.info("WebSocket connection established")
            
            # Update initial device statuses
            await self._async_update_data()
            
            return True
        except Exception as error:
            _LOGGER.error("Error setting up coordinator: %s", error)
            return False

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.debug("Starting periodic update for all devices")
            
            # Get all device statuses in one call
            devices = await self.api_client.async_get_devices
            if not devices:
                _LOGGER.warning("No devices found during update")
                raise UpdateFailed("No devices found")
            
            # Update coordinator data
            self._devices = devices
            self.data = devices
            _LOGGER.info("Successfully updated %d devices", len(devices))
            
            return self._devices
            
        except Exception as error:
            _LOGGER.error("Error updating device data: %s", error)
            raise UpdateFailed(f"Error communicating with API: {error}")

    async def async_refresh_device(self, device_id: str) -> None:
        """Manually refresh a specific device's status."""
        try:
            if device_id not in self._devices:
                _LOGGER.warning("Device %s not found", device_id)
                return

            _LOGGER.debug("Manually refreshing device %s", device_id)
            
            # Get all device statuses in one call since it's more efficient
            devices = await self.api_client.async_get_devices
            if devices and device_id in devices:
                self._devices = devices
                self.data = devices
                self.async_set_updated_data(self._devices)
                _LOGGER.info("Manually refreshed device %s", device_id)
            else:
                _LOGGER.warning("Device %s not found in update response", device_id)
                
        except Exception as error:
            _LOGGER.error("Error refreshing device %s: %s", device_id, error)

    async def async_refresh_all_devices(self) -> None:
        """Manually refresh all devices' status."""
        try:
            _LOGGER.debug("Manually refreshing all devices")
            devices = await self.api_client.async_get_devices
            if devices:
                self._devices = devices
                self.data = devices
                self.async_set_updated_data(self._devices)
                _LOGGER.info("Successfully refreshed %d devices", len(devices))
            else:
                _LOGGER.warning("No devices found during refresh")
                
        except Exception as error:
            _LOGGER.error("Error refreshing devices: %s", error)

    async def async_control_device(self, puid: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Control a device."""
        try:
            _LOGGER.debug(
                "Controlling device %s with properties: %s",
                puid,
                properties
            )
            
            result = await self.api_client.async_control_device(puid=puid, properties=properties)
            _LOGGER.debug("Control result: %s", result)
            # Refresh device status immediately after control
            # await self.async_refresh_device(puid)
            
            _LOGGER.info(
                "Successfully controlled device %s: %s",
                puid,
                result
            )
            return result
            
        except Exception as error:
            _LOGGER.error("Error controlling device %s: %s", puid, error)
            raise UpdateFailed(error) from error

    def get_device(self, device_id: str) -> DeviceInfo | None:
        """Get device by ID or puid."""
        # 首先尝试直接通过device_id查找
        # _LOGGER.debug("Trying to find device with ID: %s", device_id)
        # _LOGGER.debug("Available devices: %s", [f"{d.device_id} (puid: {d.puid}, type: {d.type_code}-{d.feature_code})" for d in self._devices.values()])
        
        device = self._devices.get(device_id)
        if device:
            _LOGGER.debug("Found device by device_id: %s", device_id)
            return device
            
        # 如果找不到，尝试通过puid查找
        _LOGGER.debug("Device not found by device_id, trying puid")
        for dev in self._devices.values():
            if getattr(dev, 'puid', None) == device_id:
                _LOGGER.debug("Found device by puid: %s", device_id)
                return dev
        
        _LOGGER.warning("Device not found with ID or puid: %s", device_id)        
        return None

    async def async_unload(self) -> None:
        """Unload the coordinator."""
        if self._websocket and self._websocket_connected:
            await self._websocket.async_disconnect()
            self._websocket = None
            self._websocket_connected = False
            _LOGGER.debug("WebSocket connection closed")
            
        await self.api_client.async_cleanup()
        _LOGGER.debug("Coordinator unloaded")

    @callback
    def _handle_ws_message(self, message: dict[str, Any]) -> None:
        """Handle websocket message."""
        import json
        import base64

        _LOGGER.debug("Starting to handle websocket message: %s", message)
        try:
            msg_type = message.get("msgTypeCode")
            _LOGGER.debug("Message type: %s", msg_type)
            if msg_type not in ["status_wifistatus", "status_devicestatus"]:
                return

            # Parse content field which is a JSON string
            content = message.get("content", "{}")
            _LOGGER.debug("Raw content: %s", content)
            if not isinstance(content, str):
                _LOGGER.warning("Content is not a string: %s", type(content))
                return

            try:
                content_data = json.loads(content)
                _LOGGER.debug("Parsed message content: %s", content_data)
                

                device_id = content_data.get("puid")
                
                _LOGGER.debug("Processing message for device: %s", device_id)
                _LOGGER.debug("Available devices: %s", [f"{d.device_id} (puid: {d.puid}, type: {d.type_code}-{d.feature_code})" for d in self._devices.values()])
                
                # Find device by puid instead of direct dictionary lookup
                device = None
                device_key = None
                for key, dev in self._devices.items():
                    if dev.puid == device_id:
                        device = dev
                        device_key = key
                        _LOGGER.debug("Found device with puid %s, device_id: %s", device_id, key)
                        break
                
                if device and device_key:
                    _LOGGER.debug("Found device %s in devices list", device_id)
                    device_data = device.to_dict()
                    _LOGGER.debug("Current device data: %s", device_data)
                    
                    # Update device data based on message type
                    if msg_type == "status_wifistatus":
                        # Update online status
                        online_status = content_data.get("onlinestats")
                        if online_status is not None:
                            device_data["offlineState"] = 0 if int(online_status) == 1 else 1
                            _LOGGER.debug(
                                "Updated device %s online status: %s",
                                device_id,
                                "online" if online_status == 1 else "offline"
                            )
                    else:  # status_devicestatus
                        # Update device status attributes
                        status = content_data.get("status")
                        properties = content_data.get("properties", {})
                        
                        # Handle base64 encoded status if present
                        if status and isinstance(status, str):
                            try:
                                decoded_status = base64.b64decode(status).decode('utf-8')
                                status_json = json.loads(decoded_status)
                                _LOGGER.debug("Decoded status: %s", status_json)
                                if status_json and isinstance(status_json, dict):
                                    # Update device status with decoded values
                                    for key, value in status_json.items():
                                        device_data["statusList"][key] = value
                            except Exception as e:
                                _LOGGER.warning("Failed to decode status: %s", e)
                        
                        # Update with properties if available
                        if properties and isinstance(properties, dict):
                            for key, value in properties.items():
                                device_data["statusList"][key] = value
                            _LOGGER.debug("Updated device status with properties: %s", properties)
                    
                    # Update device in coordinator
                    updated_device = DeviceInfo(device_data)
                    self._devices[device_key] = updated_device
                    self.data = self._devices
                    
                    # Get device type and parse status using appropriate parser
                    device_type = updated_device.get_device_type()
                    if device_type:
                        try:
                            from .devices import get_device_parser
                            parser = get_device_parser(device_type.type_code, device_type.feature_code)
                            _LOGGER.debug("Using parser for device type %s-%s", device_type.type_code, device_type.feature_code)
                            
                            # No need to parse status here, it will be parsed when accessed by climate entity
                            _LOGGER.debug("Device status updated: %s", updated_device.status)
                        except Exception as err:
                            _LOGGER.error("Failed to get device parser: %s", err)
                    
                    # Notify listeners of the update
                    self.hass.loop.call_soon_threadsafe(
                        self.async_set_updated_data,
                        self._devices
                    )
                    _LOGGER.info("Device %s updated via WebSocket", device_id)
                else:
                    _LOGGER.debug("Device with puid %s not found in devices list", device_id)
                
            except json.JSONDecodeError as e:
                _LOGGER.warning("Failed to parse message content: %s", e)
                
        except Exception as error:
            _LOGGER.error("Error handling websocket message: %s", error, exc_info=True)
