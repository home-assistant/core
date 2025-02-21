"""Support for Satel Integra devices."""

import collections
import logging

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUTS,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_CONF_ARM_HOME_MODE,
    DEFAULT_PORT,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_ZONES_UPDATED,
    ZONES,
    SatelConfigEntry,
    SatelData,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH]


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string,
    }
)
EDITABLE_OUTPUT_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})
PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)


def is_alarm_code_necessary(value):
    """Check if alarm code must be configured."""
    if value.get(CONF_SWITCHABLE_OUTPUTS) and CONF_CODE not in value:
        raise vol.Invalid("You need to specify alarm code to use switchable_outputs")

    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_CODE): cv.string,
                vol.Optional(CONF_DEVICE_PARTITIONS, default={}): {
                    vol.Coerce(int): PARTITION_SCHEMA
                },
                vol.Optional(CONF_ZONES, default={}): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_OUTPUTS, default={}): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_SWITCHABLE_OUTPUTS, default={}): {
                    vol.Coerce(int): EDITABLE_OUTPUT_SCHEMA
                },
            },
            is_alarm_code_necessary,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up  Satel Integra from YAML."""

    if config := hass_config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, config))

    return True


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Process YAML import."""

    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )

        if result.get("type") == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml_import_issue_cannot_connect",
                breaks_in_ha_version="2025.8.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_cannot_connect",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Satel Integra",
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.8.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Satel Integra",
        },
    )


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
