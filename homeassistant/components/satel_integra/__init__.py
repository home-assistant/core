"""Support for Satel Integra devices."""
import collections
import logging

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_CODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUTS,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DATA_SATEL_CONFIG,
    DEFAULT_CONF_ARM_HOME_MODE,
    DEFAULT_PORT,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_ZONES_UPDATED,
    SUPPORTED_PLATFORMS,
    ZONES,
)

_LOGGER = logging.getLogger(__name__)


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_NAME): cv.string,
        vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string,
    }
)
EDITABLE_OUTPUT_SCHEMA = vol.Schema({vol.Required(CONF_ZONE_NAME): cv.string})
PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_NAME): cv.string,
        vol.Optional(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)


def is_alarm_code_necessary(value):
    """Check if alarm code must be configured."""
    if value.get(CONF_SWITCHABLE_OUTPUTS) and CONF_DEVICE_CODE not in value:
        raise vol.Invalid("You need to specify alarm code to use switchable_outputs")

    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_HOST),
            cv.deprecated(CONF_PORT, default=DEFAULT_PORT),
            cv.deprecated(CONF_DEVICE_CODE),
            {
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Satel Integra component."""

    conf = config.get(DOMAIN)

    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    conf = dict(conf)
    hass.data[DATA_SATEL_CONFIG] = conf

    # Only import if we haven't before.
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    if (conf := hass.data.get(DATA_SATEL_CONFIG)) is None:
        _conf = await async_integration_yaml_config(hass, DOMAIN)
        if not _conf or DOMAIN not in _conf:
            _LOGGER.warning(
                "No `satel:` key found in configuration.yaml. See "
                "https://www.home-assistant.io/integrations/satel_integra/ "
                "for satel entity configuration documentation"
            )
            # generate defaults
            conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
        else:
            conf = _conf[DOMAIN]

    zones = conf[CONF_ZONES]
    outputs = conf[CONF_OUTPUTS]
    switchable_outputs = conf[CONF_SWITCHABLE_OUTPUTS]
    partitions = conf[CONF_DEVICE_PARTITIONS]

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    monitored_outputs = collections.OrderedDict(
        list(outputs.items()) + list(switchable_outputs.items())
    )

    try:
        controller = AsyncSatel(
            host,
            port,
            hass.loop,
            zones,
            monitored_outputs,
            partitions,
        )

        result = await controller.connect()

        if not result:
            raise Exception("Controller failed to connect")

    except Exception as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DATA_SATEL_CONFIG] = conf
    hass.data[DOMAIN] = controller

    @callback
    def _close(*_):
        controller.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    _LOGGER.debug("Arm home config: %s, mode: %s ", conf, conf.get(CONF_ARM_HOME_MODE))

    hass.config_entries.async_setup_platforms(
        entry,
        list(SUPPORTED_PLATFORMS),
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

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a given config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Satel platforms."""
    #  if not loaded directly return
    if not hass.data.get(DOMAIN):
        return True

    controller: AsyncSatel = hass.data[DOMAIN]

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        list(SUPPORTED_PLATFORMS),
    )
    if unload_ok:
        controller.close()
        hass.data.pop(DOMAIN)
        hass.data.pop(DATA_SATEL_CONFIG)

    return unload_ok
