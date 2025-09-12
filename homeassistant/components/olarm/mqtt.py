"""MQTT client wrapper for the Olarm integration."""

from __future__ import annotations

import asyncio
import logging
import ssl

from aiohttp import ClientResponseError
from olarmflowclient import OlarmFlowClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN
from .coordinator import OlarmDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class OlarmFlowClientMQTT:
    """MQTT client wrapper for Olarm devices.

    This class manages the MQTT connection to Olarm's MQTT Brokers, handles OAuth2 token refresh
    when the access token expires and routes incoming device messages to the data coordinator.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        olarm_client: OlarmFlowClient,
        coordinator: OlarmDataUpdateCoordinator,
    ) -> None:
        """Initialize the Olarm MQTT client wrapper."""

        self._hass = hass
        self._oauth_session = oauth_session
        self._coordinator = coordinator

        # user and device ref
        self._user_id = entry.data["user_id"]
        self.device_id = entry.data["device_id"]

        # olarm connect client
        self._olarm_flow_client = olarm_client

    async def _ensure_valid_token(self) -> None:
        """Ensure the OAuth2 access token is valid and refresh if needed.

        Checks if access token has expired and if not uses refresh token to fetch new.
        """
        try:
            # Check if token needs refresh
            token_valid = self._oauth_session.valid_token
            if not token_valid:
                _LOGGER.debug("Access token expired, refreshing")

            await self._oauth_session.async_ensure_token_valid()
            new_token = self._oauth_session.token["access_token"]
            expires_at = self._oauth_session.token["expires_at"]

            # Log token info (without exposing the actual token)
            _LOGGER.debug("Access token expires at: %s ", expires_at)

            await self._olarm_flow_client.update_access_token(new_token, expires_at)
        except ClientResponseError as e:
            _LOGGER.error("Failed to refresh OAuth2 token: %s", e)

            # Check if this is an invalid_grant error (status 400) that indicates expired/invalid refresh token
            if e.status == 400:
                _LOGGER.error(
                    "OAuth2 refresh token is invalid (status 400). Integration will remain in error state"
                    "Please remove and re-add the integration to fix authentication"
                )
                raise ConfigEntryNotReady(
                    "OAuth2 refresh token is invalid. Please remove and re-add the integration."
                ) from e

            # For other HTTP errors, treat as temporary and retry
            raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from e
        except Exception as e:
            _LOGGER.error("Failed to refresh OAuth2 token: %s", e)
            raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from e

    def _mqtt_reconnection_callback(self) -> None:
        """Thread-safe callback for MQTT reconnection events."""
        # Schedule the token refresh in the main event loop
        asyncio.run_coroutine_threadsafe(
            self._handle_mqtt_reconnection(), self._hass.loop
        )

    async def _handle_mqtt_reconnection(self) -> None:
        """Handle MQTT reconnection by refreshing the OAuth2 token.

        Handles MQTT reconnection when connection is lost, also checks access token hasnt expired and gets a new one if required.
        """
        _LOGGER.debug("Handling MQTT reconnection - refreshing token")
        try:
            # Ensure we have a valid token before reconnecting
            await self._ensure_valid_token()
            _LOGGER.debug("Token refreshed successfully for MQTT reconnection")
        except (ConfigEntryNotReady, OSError, TimeoutError) as e:
            _LOGGER.error("Failed to refresh token for MQTT reconnection: %s", e)

    async def init_mqtt(self) -> None:
        """Initialize and connect to the Olarm MQTT service."""

        _LOGGER.debug("Attempting to connect to Olarm MQTT Service")

        try:
            # Ensure token is valid before connecting to MQTT
            await self._ensure_valid_token()

            # Set up the reconnection callback before starting MQTT
            self._olarm_flow_client.set_mqtt_reconnection_callback(
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
                return self._olarm_flow_client.start_mqtt(
                    self._user_id, ssl_context, client_id_suffix
                )

            # Run the blocking MQTT connection in an executor to avoid blocking the event loop
            await asyncio.wait_for(
                self._hass.async_add_executor_job(start_mqtt_with_ssl),
                timeout=30.0,
            )

            # Subscribe to Device Events
            self._olarm_flow_client.subscribe_to_device(
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

    def mqtt_message_callback(self, topic: str, payload: str) -> None:
        """Handle incoming MQTT messages from the Olarm device."""

        _LOGGER.debug("MQTT message received: topic = %s, payload = %s", topic, payload)
        self._hass.loop.call_soon_threadsafe(
            self._coordinator.async_update_from_mqtt, payload
        )

    async def async_stop(self) -> None:
        """Stop the MQTT client and clean up connections."""

        if self._olarm_flow_client:
            # stop_mqtt is synchronous, so run it in an executor
            await self._hass.async_add_executor_job(self._olarm_flow_client.stop_mqtt)
