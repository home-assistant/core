"""API client for Hisense ConnectLife - Home Assistant Adapter."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import aiohttp
from connectlife_cloud import ConnectLifeCloudClient, ConnectLifeWebSocket
from connectlife_cloud.devices.base import BaseDeviceParser

from homeassistant.core import HomeAssistant

from .const import CLIENT_ID, CLIENT_SECRET
from .models import DeviceInfo as HisenseDeviceInfo, HisenseApiError
from .oauth2 import OAuth2Session

_LOGGER = logging.getLogger(__name__)


class HisenseApiClient:
    """Home Assistant adapter for ConnectLife Cloud API client.

    This wrapper serves several purposes:
    1. OAuth2 Token Management: Automatically refreshes tokens via OAuth2Session
    2. Data Transformation: Converts connectlife_cloud device objects to
       Home Assistant-specific HisenseDeviceInfo dataclass
    3. WebSocket Lifecycle: Manages persistent WebSocket connection for real-time updates
    4. Device Caching: Maintains device state across coordinator updates
    """

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

        self._devices: dict[str, HisenseDeviceInfo] = {}
        self._websocket: ConnectLifeWebSocket | None = None

    @property
    async def async_get_devices(self) -> dict[str, HisenseDeviceInfo]:
        """Get list of devices with their current status.

        Returns:
            Dictionary mapping device_id to DeviceInfo
        """
        _LOGGER.debug("Fetching device list with status")

        try:
            # Get access token
            access_token = await self.oauth_session.async_get_access_token()

            # Use the cloud client to get devices with parsers
            devices_with_parsers = await self.client.get_devices_with_parsers(
                access_token
            )

            # Update power consumption for devices that support it
            for device_id, (device, parser) in devices_with_parsers.items():
                # Check if device has power consumption attribute
                if "f_power_consumption" in parser.attributes:
                    try:
                        await self.client.update_power_consumption(device, access_token)
                    except (TimeoutError, aiohttp.ClientError) as power_err:
                        _LOGGER.debug(
                            "Network error updating power consumption for %s: %s",
                            device_id,
                            power_err,
                        )

                try:
                    await self.client.update_self_check_data(device, access_token)
                except (TimeoutError, aiohttp.ClientError) as self_check_err:
                    _LOGGER.debug(
                        "Network error updating self-check data for %s: %s",
                        device_id,
                        self_check_err,
                    )

                # Convert to Home Assistant specific device representation
                hisense_device = HisenseDeviceInfo(device.to_dict())
                self._devices[device_id] = hisense_device

        except Exception as err:
            _LOGGER.error("Failed to fetch devices: %s", err)
            raise HisenseApiError(f"Error communicating with API: {err}") from err
        else:
            return self._devices

    async def async_setup_websocket(
        self, message_callback: Callable[[dict[str, Any]], None]
    ) -> None:
        """Ensure the WebSocket is connected and streaming updates."""
        if self._websocket is None:
            self._websocket = ConnectLifeWebSocket(
                client=self.client,
                session=self.client.session,
                token_getter=self.oauth_session.async_get_access_token,
                message_callback=message_callback,
                loop=self.hass.loop,
            )

            await self._websocket.async_connect()

    async def async_cleanup(self) -> None:
        """Clean up resources."""
        if self._websocket is not None:
            await self._websocket.async_disconnect()
            self._websocket = None

        await self.client.close()

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
            raise HisenseApiError("Control failed")  # noqa: TRY301

        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

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
        return self.client._parsers  # noqa: SLF001

    @property
    def static_data(self) -> dict[str, Any]:
        """Get static data dictionary.

        This property provides backward compatibility for diagnostics and tests.

        Returns:
            Dictionary mapping device_id to static data
        """
        return self.client._static_data  # noqa: SLF001
