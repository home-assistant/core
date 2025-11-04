"""MQTT client wrapper for the Olarm integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from olarmflowclient import MqttConnectError, MqttTimeoutError, OlarmFlowClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, issue_registry as ir

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

        self._hass: HomeAssistant = hass
        self._oauth_session: config_entry_oauth2_flow.OAuth2Session = oauth_session
        self._coordinator: OlarmDataUpdateCoordinator = coordinator

        # user and device ref
        self._user_id: str = entry.data["user_id"]
        self.device_id: str = entry.data["device_id"]

        # olarm connect client
        self._olarm_flow_client: OlarmFlowClient = olarm_client

        # get the assigned client ID suffix from config (default to "1" for backward compatibility)
        self.client_id_suffix: str = str(entry.data.get("client_id_suffix", "1"))

    def _mqtt_status_callback(
        self,
        status: Literal["connecting", "connected", "disconnected", "reconnecting"],
        info: dict[str, Any],
    ) -> None:
        """Thread-safe callback for MQTT connection status changes."""

        if status == "connecting":
            _LOGGER.debug("MQTT connecting to Olarm service")
        elif status == "connected":
            _LOGGER.debug("MQTT connected to Olarm service")
            # Clear any disconnection repair issues
            ir.async_delete_issue(
                self._hass, DOMAIN, f"mqtt_disconnected_{self.device_id}"
            )
        elif status == "disconnected":
            reason = info.get("reason", "Unknown reason")
            _LOGGER.error("MQTT disconnected from Olarm service: %s", reason)
            # Use refresh token to fetch new access tokens if expired
            asyncio.run_coroutine_threadsafe(
                self._coordinator.async_ensure_token_valid(), self._hass.loop
            )
            # Create repair issue for disconnection
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                f"mqtt_disconnected_{self.device_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="mqtt_disconnected",
                translation_placeholders={"reason": reason},
            )
        elif status == "reconnecting":
            reason = info.get("reason", "Unknown reason")
            _LOGGER.debug("MQTT reconnecting to Olarm service: %s", reason)
            # Use refresh token to fetch new access tokens if expired
            asyncio.run_coroutine_threadsafe(
                self._coordinator.async_ensure_token_valid(), self._hass.loop
            )

    async def init_mqtt(self) -> None:
        """Initialize and connect to the Olarm MQTT service."""

        _LOGGER.debug("Attempting to connect to Olarm MQTT Service")

        # Set up the connection status callback before starting MQTT
        self._olarm_flow_client.set_mqtt_status_callback(self._mqtt_status_callback)

        try:
            # Ensure token is valid before connecting to MQTT
            await self._coordinator.async_ensure_token_valid()

            # Startup MQTT
            await self._olarm_flow_client.start_mqtt_async(
                user_id=self._user_id,
                client_id_suffix=self.client_id_suffix,
                event_loop=self._hass.loop,
                timeout=10.0,
            )

            # Subscribe to Device Events
            self._olarm_flow_client.subscribe_to_device(
                self.device_id, self.mqtt_message_callback
            )
            _LOGGER.debug("Successfully connected to Olarm MQTT Service")

        except (MqttTimeoutError, MqttConnectError) as e:
            _LOGGER.error("Failed to connect to Olarm MQTT Service: %s", e)
            raise

    def mqtt_message_callback(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle incoming MQTT messages from the Olarm device."""

        _LOGGER.debug("MQTT message received: topic = %s, payload = %s", topic, payload)
        self._hass.loop.call_soon_threadsafe(
            self._coordinator.async_update_from_mqtt, payload
        )

    async def async_stop(self) -> None:
        """Stop the MQTT client and clean up connections."""
        if self._olarm_flow_client:
            try:
                # stop_mqtt is synchronous, so run it in an executor
                await self._hass.async_add_executor_job(
                    self._olarm_flow_client.stop_mqtt
                )
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Error stopping MQTT client: %s", e)
            finally:
                # Clean up any repair issues
                ir.async_delete_issue(
                    self._hass, DOMAIN, f"mqtt_disconnected_{self.device_id}"
                )
