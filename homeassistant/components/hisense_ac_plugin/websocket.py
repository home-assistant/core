import asyncio
import json
import logging
import uuid
import base64
from typing import Any, Callable, Optional
import time

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import ApiClientProtocol, NotificationInfo

_LOGGER = logging.getLogger(__name__)

class HisenseWebSocket:
    """WebSocket client for Hisense AC."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ApiClientProtocol,
        message_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Initialize the WebSocket client."""
        self.hass = hass
        self.api_client = api_client
        self.message_callback = message_callback
        self.session = async_get_clientsession(hass)
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._phone_code: str = ""
        self._notification_info: Optional[NotificationInfo] = None
        self._task: Optional[asyncio.Task] = None
        self._closing = False
        self._ping_interval = 30
        self._last_ping = 0
        self._fail_count = 0
        self._max_fails = 3
        self._last_message_time = 0  # 记录上一次处理消息的时间

    async def _generate_phone_code(self) -> str:
        """Generate a phone code (UUID)."""
        phone_code = str(uuid.uuid4())
        _LOGGER.debug("Generated new phone code: %s", phone_code)
        return phone_code

    async def _register_phone_code(self, phone_code: str) -> bool:
        """Register phone code with the server."""
        _LOGGER.debug("Registering phone code: %s", phone_code)
        try:
            response = await self.api_client._api_request(
                "POST",
                "/msg/registerPhoneDevice",
                data={"phoneCode": phone_code}
            )
            success = response.get("resultCode") == 0
            _LOGGER.debug("Phone code registration %s", "successful" if success else "failed")
            return success
        except Exception as err:
            _LOGGER.error("Failed to register phone code: %s", err)
            return False

    async def _get_notification_info(self, phone_code: str) -> Optional[NotificationInfo]:
        """Get notification server information."""
        _LOGGER.debug("Fetching notification info for phone code: %s", phone_code)
        try:
            response = await self.api_client._api_request(
                "GET",
                "/msg/get_msg_and_channels",
                data={
                    "pageNo": "1",
                    "pageSize": "10",
                    "phoneCode": phone_code,
                    "queryType": 2
                }
            )
            notification_info = NotificationInfo.from_json(response)
            _LOGGER.debug("Received notification info - Server: %s:%s", 
                         notification_info.push_server_ip if notification_info else "N/A",
                         notification_info.push_server_ssl_port if notification_info else "N/A")
            return notification_info
        except Exception as err:
            _LOGGER.error("Failed to get notification info: %s", err)
            return None

    async def _connect_ws(self) -> None:
        """Establish WebSocket connection."""
        if not self._notification_info or not self._phone_code:
            _LOGGER.error("Missing notification info or phone code")
            return

        channel = (self._notification_info.push_channels[0].push_channel
                  if self._notification_info.push_channels else "")
        if not channel:
            _LOGGER.error("No push channel available")
            return

        _LOGGER.debug("Attempting WebSocket connection - Channel: %s", channel)

        try:
            # Get fresh token before connection
            access_token = await self.api_client.oauth_session.async_get_access_token()

            ws_url = (
                f"wss://{self._notification_info.push_server_ip}:"
                f"{self._notification_info.push_server_ssl_port}/ws/{channel}"
                f"?phoneCode={self._phone_code}&token={access_token}"
            )
            _LOGGER.debug("WebSocket URL: %s", ws_url)

            self._ws = await self.session.ws_connect(
                ws_url,
                heartbeat=self._ping_interval,
                ssl=True
            )
            _LOGGER.info("WebSocket connection established")
            self._fail_count = 0
            await self._listen()

        except aiohttp.ClientError as err:
            _LOGGER.error("WebSocket connection failed: %s", err)
            self._fail_count += 1
            if self._fail_count >= self._max_fails:
                _LOGGER.error("Max connection failures reached")
                return

            # Exponential backoff for reconnection attempts
            retry_delay = min(30, 5 * (2 ** (self._fail_count - 1)))
            _LOGGER.debug("Waiting %s seconds before reconnecting", retry_delay)
            await asyncio.sleep(retry_delay)

            if not self._closing:
                # Refresh connection info before retry
                self._notification_info = await self._get_notification_info(self._phone_code)
                if self._notification_info:
                    await self._connect_ws()

    async def _listen(self) -> None:
        """Listen for messages on WebSocket."""
        if not self._ws:
            return

        try:
            _LOGGER.debug("Starting WebSocket message listener")
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    current_time = time.time()
                    if current_time - self._last_message_time < 1:
                        _LOGGER.debug("Skipping message due to rate limit")
                        continue
                    self._last_message_time = current_time  # 更新上一次处理消息的时间

                    _LOGGER.debug("Received raw WebSocket message: %s", msg.data)
                    try:
                        # Decode base64 and then UTF-8
                        base64_decoded = base64.b64decode(msg.data)
                        decoded_content = base64_decoded.decode('utf-8')
                        _LOGGER.debug("Decoded message content: %s", decoded_content)
                        
                        data = json.loads(decoded_content)
                        self.message_callback(data)
                    except base64.binascii.Error as err:
                        _LOGGER.error("Failed to decode base64 message: %s", err)
                    except UnicodeDecodeError as err:
                        _LOGGER.error("Failed to decode UTF-8 content: %s", err)
                    except json.JSONDecodeError as err:
                        _LOGGER.error("Failed to parse JSON message: %s", err)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", self._ws.exception())
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    _LOGGER.debug("WebSocket connection closed")
                    break
                else:
                    _LOGGER.debug("Received unknown message type: %s", msg.type)
        except Exception as err:
            _LOGGER.error("WebSocket listener error: %s", err)
        finally:
            if not self._closing and self._fail_count < self._max_fails:
                self.hass.loop.create_task(self._delayed_reconnect())

    async def _delayed_reconnect(self) -> None:
        """Handle reconnection with delay."""
        try:
            # Add delay before reconnection attempt
            await asyncio.sleep(5)
            # Refresh connection info
            self._notification_info = await self._get_notification_info(self._phone_code)
            if self._notification_info:
                await self._connect_ws()
        except Exception as err:
            _LOGGER.error("Error during reconnection: %s", err)

    async def async_connect(self) -> None:
        """Connect to WebSocket server."""
        try:
            # Step 1: Generate phone code
            self._phone_code = await self._generate_phone_code()
            _LOGGER.debug("Generated phone code: %s", self._phone_code)

            # Step 2: Register phone code
            if not await self._register_phone_code(self._phone_code):
                _LOGGER.error("Failed to register phone code")
                return

            # Step 3: Get notification info
            self._notification_info = await self._get_notification_info(self._phone_code)
            if not self._notification_info:
                _LOGGER.error("Failed to get notification info")
                return

            # Set ping interval from server config
            self._ping_interval = self._notification_info.hb_interval
            self._max_fails = self._notification_info.hb_fail_times

            # Step 4: Connect WebSocket
            self._closing = False
            self._task = self.hass.async_create_task(self._connect_ws())
            _LOGGER.debug("WebSocket connection task created")

        except Exception as err:
            _LOGGER.error("Failed to connect to WebSocket: %s", err)

    async def async_disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        self._closing = True
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._ws = None
        self._task = None
        _LOGGER.debug("WebSocket disconnected")
