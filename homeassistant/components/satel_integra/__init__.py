"""Support for Satel Integra devices."""

import collections
import logging

from satel_integra.satel_integra import AsyncSatel

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUTS,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONES,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_ZONES_UPDATED,
    ZONES,
    SatelConfigEntry,
    SatelData,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up  Satel Integra from YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Set up  Satel Integra from a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    partitions = entry.options.get(CONF_DEVICE_PARTITIONS, {})
    zones = entry.options.get(CONF_ZONES, {})
    outputs = entry.options.get(CONF_OUTPUTS, {})
    switchable_outputs = entry.options.get(CONF_SWITCHABLE_OUTPUTS, {})

    monitored_outputs = collections.OrderedDict(
        list(outputs.items()) + list(switchable_outputs.items())
    )

    controller = AsyncSatel(host, port, hass.loop, zones, monitored_outputs, partitions)

    result = await controller.connect()

    if not result:
        raise ConfigEntryNotReady("Controller failed to connect")

    entry.runtime_data = SatelData(controller)

    @callback
    def _close(*_):
        controller.close()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    @callback
    def alarm_status_update_callback():
        """Send status update received from alarm to Home Assistant."""
        _LOGGER.debug("Sending request to update panel state")
        async_dispatcher_send(hass, SIGNAL_PANEL_MESSAGE)

    @callback
    def zones_update_callback(status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback, status: %s", status)
        async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, status[ZONES])

    @callback
    def outputs_update_callback(status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Outputs updated callback , status: %s", status)
        async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, status["outputs"])

    # Create a task instead of adding a tracking job, since this task will
    # run until the connection to satel_integra is closed.
    hass.loop.create_task(controller.keep_alive())
    hass.loop.create_task(
        controller.monitor_status(
            alarm_status_update_callback, zones_update_callback, outputs_update_callback
        )
    )

    return True


async def update_listener(hass: HomeAssistant, entry: SatelConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Unloading the Satel platforms."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        controller = entry.runtime_data.controller
        controller.close()

    return unload_ok
