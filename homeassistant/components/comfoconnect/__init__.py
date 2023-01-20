"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
from pycomfoconnect import Bridge, ComfoConnect
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    _LOGGER,
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
    SIGNAL_COMFOCONNECT_UPDATE_RECEIVED,
)

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

PLATFORMS = [Platform.FAN, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ComfoConnect bridge."""

    # No more setup from configuration.yaml, only remember config for import

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    _LOGGER.warning(
        "Configuring ComfoConnect using YAML is being removed. Your existing "
        "YAML configuration has been imported into the UI automatically. Remove "
        "the ComfoConnect YAML configuration from your configuration.yaml file and "
        "restart Home Assistant to fix this issue"
    )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    # Already imported, then quit
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return True

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SOURCE_IMPORT] = conf

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ComfoConnect bridge."""

    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    token = entry.data[CONF_TOKEN]
    user_agent = entry.data[CONF_USER_AGENT]
    pin = entry.data[CONF_PIN]

    # Run discovery on the configured ip
    bridges = Bridge.discover(entry.data[CONF_HOST])
    if not bridges:
        _LOGGER.error("Could not connect to ComfoConnect bridge on %s", host)
        raise ConfigEntryNotReady

    bridge = bridges[0]

    # Setup ComfoConnect Bridge
    ccb = ComfoConnectBridge(hass, bridge, name, token, user_agent, pin)

    # hass.data[DOMAIN] = ccb
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = ccb

    # Start connection with bridge
    ccb.connect()

    # Schedule disconnect on shutdown
    def _shutdown(_event):
        ccb.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Comfoconnect config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    # if not hass.data[DOMAIN]:
    #     del hass.data[DOMAIN]

    return unload_ok


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

    def connect(self):
        """Connect with the bridge."""
        _LOGGER.debug("Connecting with bridge")
        self.comfoconnect.connect(True)

    def disconnect(self):
        """Disconnect from the bridge."""
        _LOGGER.debug("Disconnecting from bridge")
        self.comfoconnect.disconnect()

    def sensor_callback(self, var, value):
        """Notify listeners that we have received an update."""
        _LOGGER.debug("Received update for %s: %s", var, value)
        dispatcher_send(
            self.hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(var), value
        )
