"""The coordinator for the olarm integration to handle API and MQTT connections."""

from __future__ import annotations

import asyncio
import logging
import ssl

from olarmconnect import OlarmConnect, OlarmConnectApiError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OlarmConnectCoordinator:
    """Manages an individual olarms config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        user_id: str,
        device_id: str,
        access_token: str,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Create a new instance of the OlarmBroker."""
        self._hass = hass
        self._oauth_session = oauth_session

        # user props
        # self._refresh_token = refresh_token
        self._user_id = user_id

        # device props
        self.device_id = device_id
        self.device_name = None
        self.device_state = None
        self.device_links = None
        self.device_io = None
        self.device_profile = None
        self.device_profile_links = None
        self.device_profile_io = None

        # olarm connect client
        self._olarm_connect_client = OlarmConnect(access_token)

    async def _ensure_valid_token(self):
        """Ensure the access token is valid and refresh if needed."""
        try:
            # Check if token needs refresh
            token_valid = self._oauth_session.valid_token
            if not token_valid:
                _LOGGER.debug("Access token expired, refreshing")
            else:
                _LOGGER.debug("Access token is still valid")

            await self._oauth_session.async_ensure_token_valid()
            new_token = self._oauth_session.token["access_token"]
            expires_at = self._oauth_session.token["expires_at"]

            # Log token info (without exposing the actual token)
            _LOGGER.debug("Access token expires at: %s ", expires_at)

            await self._olarm_connect_client.update_access_token(new_token, expires_at)
        except Exception as e:
            _LOGGER.error("Failed to refresh OAuth2 token: %s", e)
            raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from e

    def _mqtt_reconnection_callback(self):
        """Thread-safe callback for MQTT reconnection - called from MQTT thread."""
        # Schedule the token refresh in the main event loop
        asyncio.run_coroutine_threadsafe(
            self._handle_mqtt_reconnection(), self._hass.loop
        )

    async def _handle_mqtt_reconnection(self):
        """Handle MQTT reconnection with token refresh."""
        _LOGGER.debug("Handling MQTT reconnection - refreshing token")
        try:
            # Ensure we have a valid token before reconnecting
            await self._ensure_valid_token()
            _LOGGER.debug("Token refreshed successfully for MQTT reconnection")
        except (ConfigEntryNotReady, OSError, TimeoutError) as e:
            _LOGGER.error("Failed to refresh token for MQTT reconnection: %s", e)

    async def get_device(self):
        """Retrieve device information from the Olarm API."""
        try:
            await self._ensure_valid_token()
            device = await self._olarm_connect_client.get_device(self.device_id)

            _LOGGER.debug("Device -> %s", device)

            self.device_name = device.get("deviceName")
            self.device_state = device.get("deviceState")
            self.device_links = device.get("deviceLinks")
            self.device_io = device.get("deviceIO")
            self.device_profile = device.get("deviceProfile")
            self.device_profile_links = device.get("deviceProfileLinks")
            self.device_profile_io = device.get("deviceProfileIO")

            _LOGGER.debug(
                "Device -> %s",
                {
                    "device_name": self.device_name,
                    "device_state": self.device_state,
                },
            )

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_area_cmd(self, device_id, area_status, area_index):
        """Send area command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_area_{area_status}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, area_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_zone_cmd(self, device_id, zone_status, zone_index):
        """Send zone bypass or unbypass command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_zone_{zone_status}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, zone_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_pgm_cmd(self, device_id, pgm_action, pgm_index):
        """Send PGM command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_pgm_{pgm_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, pgm_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_ukey_cmd(self, device_id, ukey_index):
        """Send user key command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            await self._olarm_connect_client.send_device_ukey_activate(
                device_id, ukey_index + 1
            )

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_link_output_cmd(
        self, device_id, link_id, output_action, output_index
    ):
        """Send user key command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_link_output_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, link_id, output_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_link_relay_cmd(
        self, device_id, link_id, output_action, output_index
    ):
        """Send user key command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_link_relay_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, link_id, output_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_max_output_cmd(self, device_id, output_action, output_index):
        """Send user key command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_max_output_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, output_index + 1)

        except OlarmConnectApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def init_mqtt(self):
        """Connect to the Olarm MQTT service and subscribe to device events."""
        _LOGGER.debug("Attempting to connect to Olarm MQTT Service")

        try:
            # Ensure token is valid before connecting to MQTT
            await self._ensure_valid_token()

            # Set up the reconnection callback before starting MQTT
            self._olarm_connect_client.set_mqtt_reconnection_callback(
                self._mqtt_reconnection_callback
            )

            # Olarm limits the MQTT connections per user and each needs a unique client_id
            sorted_olarm_entries = sorted(
                self._hass.config_entries.async_entries(DOMAIN),
                key=lambda x: x.entry_id,
            )
            client_id_suffix = "1"  # default fallback
            for i, entry in enumerate(sorted_olarm_entries):
                if entry.data.get("device_id") == self.device_id:
                    client_id_suffix = str(i + 1)
                    break
            _LOGGER.debug(
                "Determine client_id_suffix for mqtt connection %s: %s -> %s",
                DOMAIN,
                [entry.entry_id for entry in sorted_olarm_entries],
                client_id_suffix,
            )

            # Create a wrapper function that creates the SSL context inside the executor
            def start_mqtt_with_ssl():
                ssl_context = ssl.create_default_context()
                return self._olarm_connect_client.start_mqtt(
                    self._user_id, ssl_context, client_id_suffix
                )

            # Run the blocking MQTT connection in an executor to avoid blocking the event loop
            # Add a timeout to prevent hanging during setup
            await asyncio.wait_for(
                self._hass.async_add_executor_job(start_mqtt_with_ssl),
                timeout=30.0,
            )

            # Subscribe to Device Events (first 8 of them)
            self._olarm_connect_client.subscribe_to_device(
                self.device_id, self.mqtt_message_callback
            )
            _LOGGER.debug("Successfully connected to Olarm MQTT Service")

        except TimeoutError:
            _LOGGER.error("Timeout connecting to Olarm MQTT Service")
            raise ConfigEntryNotReady(
                "Timeout connecting to Olarm MQTT Service"
            ) from None
        except Exception as e:
            _LOGGER.error("Failed to connect to Olarm MQTT Service: %s", e)
            raise ConfigEntryNotReady(
                f"Failed to connect to Olarm MQTT Service: {e}"
            ) from e

    # Define callback function for MQTT messages
    def mqtt_message_callback(self, topic, payload):
        """Handle incoming MQTT messages."""
        _LOGGER.debug("MQTT message recevied: topic = %s, payload = %s", topic, payload)

        # only update if there is new state in the payload
        flagDispatch = False

        # save state
        if "deviceState" in payload:
            self.device_state = payload["deviceState"]
            flagDispatch = True
        if "deviceLinks" in payload:
            self.device_links = payload["deviceLinks"]
            flagDispatch = True
        if "deviceIO" in payload:
            self.device_io = payload["deviceIO"]
            flagDispatch = True

        # send update to dispatcher
        if flagDispatch:
            self._hass.loop.call_soon_threadsafe(
                async_dispatcher_send,
                self._hass,
                "olarm_mqtt_update",
                self.device_id,
                self.device_state,
                self.device_links,
                self.device_io,
            )

    async def async_refresh_token(self):
        """Manually refresh the access token."""
        try:
            await self._ensure_valid_token()
            _LOGGER.debug("Access token refreshed successfully")
        except Exception as e:
            _LOGGER.error("Failed to refresh access token: %s", e)
            raise

    async def async_stop(self):
        """Stop and clean up MQTT and API client connections."""
        if self._olarm_connect_client:
            # stop_mqtt is synchronous, so run it in an executor
            await self._hass.async_add_executor_job(
                self._olarm_connect_client.stop_mqtt
            )
