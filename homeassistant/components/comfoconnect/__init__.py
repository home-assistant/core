"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""

import logging

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
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_USER_AGENT,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = "comfoconnect_update_received_{}"

PLATFORMS = [Platform.FAN, Platform.SENSOR]

DEFAULT_NAME = "ComfoAirQ"
INTEGRATION_TITLE = "ComfoConnect"

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


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result["type"] == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result['reason']}",
                breaks_in_ha_version="2025.4.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ComfoConnect bridge."""
    if conf := config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, conf))
    return True


type ComfoConnectConfigEntry = ConfigEntry[ComfoConnectBridge]


async def async_setup_entry(
    hass: HomeAssistant, entry: ComfoConnectConfigEntry
) -> bool:
    """Set up ComfoConnect from a config entry."""
    bridges = Bridge.discover(entry.data[CONF_HOST])
    if not bridges:
        raise ConfigEntryNotReady("Could not connect to ComfoConnect bridge")
    bridge = bridges[0]
    ccb = ComfoConnectBridge(
        hass,
        bridge,
        entry.title,
        entry.data[CONF_TOKEN],
        entry.data[CONF_USER_AGENT],
        entry.data[CONF_PIN],
    )
    await hass.async_add_executor_job(ccb.connect)
    entry.runtime_data = ccb

    def _shutdown(_event: Event) -> None:
        ccb.disconnect()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ComfoConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class ComfoConnectBridge:
    """Representation of a ComfoConnect bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        bridge: Bridge,
        name: str,
        token: str,
        friendly_name: str,
        pin: int,
    ) -> None:
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

    def connect(self) -> None:
        """Connect with the bridge."""
        _LOGGER.debug("Connecting with bridge")
        self.comfoconnect.connect(True)

    def disconnect(self) -> None:
        """Disconnect from the bridge."""
        _LOGGER.debug("Disconnecting from bridge")
        self.comfoconnect.disconnect()

    def sensor_callback(self, var: str, value: str) -> None:
        """Notify listeners that we have received an update."""
        _LOGGER.debug("Received update for %s: %s", var, value)
        dispatcher_send(
            self.hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(var), value
        )
