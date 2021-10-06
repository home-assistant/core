"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

from pycomfoconnect import Bridge, ComfoConnect
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_SENSORS,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = "comfoconnect_update_received_{}"

DEVICE = None

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.Length(
                    min=32, max=32, msg="invalid token"
                ),
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): cv.string,
                vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the ComfoConnect integration."""
    if hass.config_entries.async_entries(DOMAIN):
        return True
    if DOMAIN in config:
        # import configuration using config flow
        sensors = None
        for sensor in config["sensor"]:
            if sensor.get("platform") == DOMAIN:
                sensors = sensor.get("resources")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT, "import_sensors": sensors},
                data=config[DOMAIN],
            )
        )

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    host = entry.data[CONF_HOST]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    token = entry.data.get(CONF_TOKEN, DEFAULT_TOKEN)
    user_agent = entry.data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT)
    pin = entry.data.get(CONF_PIN, DEFAULT_PIN)

    # Run discovery on the configured ip
    bridges = await hass.async_add_executor_job(Bridge.discover, host)
    if not bridges:
        raise ConfigEntryNotReady(f"Could not connect to ComfoConnect bridge on {host}")
    bridge = bridges[0]
    _LOGGER.info("Bridge found: %s (%s)", bridge.uuid.hex(), bridge.host)

    # Setup ComfoConnect Bridge
    ccb = ComfoConnectBridge(hass, bridge, name, token, user_agent, pin)
    hass.data[DOMAIN] = ccb

    # Start connection with bridge
    await ccb.connect()

    # Schedule disconnect on shutdown
    async def _shutdown(_event):
        await ccb.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    )
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)

    # remove stale entities
    selected_sensors = {
        f"{config_entry.unique_id}-{key}"
        for key in config_entry.options.get(CONF_SENSORS, [])
    }
    registry = entity_registry.async_get(hass)
    entities = entity_registry.async_entries_for_config_entry(
        registry, config_entry.entry_id
    )
    for entity in entities:
        if entity.unique_id not in selected_sensors:
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    ccb = hass.data.get(DOMAIN)
    await ccb.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class ComfoConnectBridge:
    """Representation of a ComfoConnect bridge."""

    def __init__(self, hass, bridge, name, token, friendly_name, pin):
        """Initialize the ComfoConnect bridge."""
        self.name = name
        self.hass = hass
        self.unique_id = bridge.uuid.hex()

        self.comfoconnect = ComfoConnect(
            bridge=bridge,
            local_uuid=bytes.fromhex(token),
            local_devicename=friendly_name,
            pin=pin,
        )
        self.comfoconnect.callback_sensor = self.sensor_callback

    async def connect(self):
        """Connect with the bridge."""
        _LOGGER.debug("Connecting with bridge")
        await self.hass.async_add_executor_job(self.comfoconnect.connect, True)

    async def disconnect(self):
        """Disconnect from the bridge."""
        _LOGGER.debug("Disconnecting from bridge")
        await self.hass.async_add_executor_job(self.comfoconnect.disconnect)

    def sensor_callback(self, var, value):
        """Notify listeners that we have received an update."""
        _LOGGER.debug("Received update for %s: %s", var, value)
        dispatcher_send(
            self.hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(var), value
        )
