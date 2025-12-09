"""Coordinator for Satel Integra."""

import logging

from satel_integra.satel_integra import AsyncSatel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    DOMAIN,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_ZONES_UPDATED,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
    ZONES,
)

type SatelConfigEntry = ConfigEntry[SatelIntegraCoordinator]

_LOGGER = logging.getLogger(__name__)


class SatelIntegraCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Satel Integra."""

    # _hw_version: str

    controller: AsyncSatel

    def __init__(self, hass: HomeAssistant, entry: SatelConfigEntry) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
        )

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]

        # Make sure we initialize the Satel controller with the configured entries to monitor
        partitions = [
            subentry.data[CONF_PARTITION_NUMBER]
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_PARTITION
        ]

        zones = [
            subentry.data[CONF_ZONE_NUMBER]
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ZONE
        ]

        outputs = [
            subentry.data[CONF_OUTPUT_NUMBER]
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_OUTPUT
        ]

        switchable_outputs = [
            subentry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_SWITCHABLE_OUTPUT
        ]

        monitored_outputs = outputs + switchable_outputs

        self.controller = AsyncSatel(
            host, port, hass.loop, zones, monitored_outputs, partitions
        )

        @callback
        def _close(*_):
            self.controller.close()

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)
        )

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            # model=device,
            # name=entry.get,
            name="Satel Integra",
            manufacturer="Satel",
            # hw_version=self._hw_version,
        )

    @callback
    def alarm_status_update_callback(self):
        """Send status update received from alarm to Home Assistant."""
        _LOGGER.debug("Sending request to update panel state")
        async_dispatcher_send(self.hass, SIGNAL_PANEL_MESSAGE)

    @callback
    def zones_update_callback(self, status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback, status: %s", status)
        async_dispatcher_send(self.hass, SIGNAL_ZONES_UPDATED, status[ZONES])

    @callback
    def outputs_update_callback(self, status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Outputs updated callback , status: %s", status)
        async_dispatcher_send(self.hass, SIGNAL_OUTPUTS_UPDATED, status["outputs"])

    async def start_controller(self) -> None:
        """Start controller connection."""
        result = await self.controller.connect()
        if not result:
            raise ConfigEntryNotReady("Controller failed to connect")

        # Create a task instead of adding a tracking job, since this task will
        # run until the connection to satel_integra is closed.
        self.hass.loop.create_task(self.controller.keep_alive())
        self.hass.loop.create_task(
            self.controller.monitor_status(
                self.alarm_status_update_callback,
                self.zones_update_callback,
                self.outputs_update_callback,
            )
        )
