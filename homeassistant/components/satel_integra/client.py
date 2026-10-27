"""Satel Integra client."""

from collections.abc import Callable
import logging

from satel_integra import AsyncSatel
from satel_integra.exceptions import (
    SatelConnectFailedError,
    SatelConnectionInitializationError,
    SatelMonitoringStartError,
    SatelPanelBusyError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
    CONF_ENCRYPTION_KEY,
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    DOMAIN,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)

_LOGGER = logging.getLogger(__name__)


class SatelClient:
    """Client to connect to Satel Integra."""

    controller: AsyncSatel

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the client wrapper."""
        self.hass = hass
        self.config_entry = entry
        self._connection_status_unsubscribe: Callable[[], None] | None = None

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]

        # Make sure we initialize the Satel controller
        # with the configured entries to monitor
        partitions = [
            subentry.data[CONF_PARTITION_NUMBER]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PARTITION)
        ]

        zones = [
            subentry.data[CONF_ZONE_NUMBER]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        ]

        outputs = [
            subentry.data[CONF_OUTPUT_NUMBER]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_OUTPUT)
        ]

        switchable_outputs = [
            subentry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]
            for subentry in entry.get_subentries_of_type(
                SUBENTRY_TYPE_SWITCHABLE_OUTPUT
            )
        ]

        monitored_outputs = outputs + switchable_outputs

        self.controller = AsyncSatel(
            host,
            port,
            zones,
            monitored_outputs,
            partitions,
            integration_key=entry.data[CONF_ENCRYPTION_KEY],
        )

    async def async_connect(self) -> None:
        """Start controller connection."""
        try:
            await self.controller.connect(raise_exceptions=True)
        except SatelConnectFailedError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from ex
        except SatelPanelBusyError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="panel_busy",
            ) from ex
        except SatelConnectionInitializationError as ex:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="connection_initialization_failed",
            ) from ex

        try:
            await self.controller.start(enable_monitoring=True)
        except SatelMonitoringStartError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="monitoring_start_failed",
            ) from ex

        self._connection_status_unsubscribe = (
            self.controller.add_connection_status_callback(
                self._on_connection_state_change
            )
        )
        self.config_entry.async_on_unload(self._unsubscribe_connection_status)

    async def async_close(self) -> None:
        """Close the connection."""

        self._unsubscribe_connection_status()
        await self.controller.close()

    def _unsubscribe_connection_status(self) -> None:
        """Unsubscribe from connection status updates."""
        if self._connection_status_unsubscribe is not None:
            self._connection_status_unsubscribe()
            self._connection_status_unsubscribe = None

    def _on_connection_state_change(self) -> None:
        """Handle connection state changes."""
        if self.controller.connected:
            _LOGGER.info(
                "Satel Integra device is back online: %s", self.config_entry.title
            )
        else:
            _LOGGER.info(
                "Satel Integra device is unavailable: %s", self.config_entry.title
            )
