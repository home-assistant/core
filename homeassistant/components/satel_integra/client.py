"""Satel Integra client."""

from collections.abc import Callable

from satel_integra import AsyncSatel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)


class SatelClient:
    """Client to connect to Satel Integra."""

    controller: AsyncSatel

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the client wrapper."""
        self.hass = hass
        self.config_entry = entry

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

        self.controller = AsyncSatel(host, port, zones, monitored_outputs, partitions)

    async def async_connect(
        self,
        zones_update_callback: Callable[[dict[int, int]], None],
        outputs_update_callback: Callable[[dict[int, int]], None],
        partitions_update_callback: Callable[[], None],
    ) -> None:
        """Start controller connection."""
        result = await self.controller.connect()
        if not result:
            raise ConfigEntryNotReady("Controller failed to connect")

        self.controller.register_callbacks(
            alarm_status_callback=partitions_update_callback,
            zone_changed_callback=zones_update_callback,
            output_changed_callback=outputs_update_callback,
        )

        await self.controller.start(enable_monitoring=True)

    async def async_close(self) -> None:
        """Close the connection."""

        await self.controller.close()
