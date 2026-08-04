"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""

import logging
from typing import Any

from pycomfoconnect import Bridge, ComfoConnect
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME, CONF_PIN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
    PLATFORMS,
    SIGNAL_COMFOCONNECT_UPDATE_RECEIVED,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_MODEL, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.Length(
                    min=32, max=32, msg="invalid token"
                ),
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): cv.string,
                vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
                vol.Optional(
                    CONF_NAME
                ): cv.string,  # Deprecated, kept for backwards compatibility
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up ComfoConnect from YAML by importing it into a config entry once."""
    if DOMAIN not in config:
        return True

    hass.add_job(async_setup_import(hass, config[DOMAIN]))
    return True


async def async_setup_import(hass: HomeAssistant, conf: dict[str, Any]) -> None:
    """Import ComfoConnect YAML config into a config entry and log migration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=conf,
    )

    if result.get("type") is FlowResultType.CREATE_ENTRY or (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") == "already_configured"
    ):
        _LOGGER.warning(
            "The %s YAML configuration has been migrated to the UI and can be removed "
            "from configuration.yaml",
            DOMAIN,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ComfoConnect from a config entry."""
    host = entry.data[CONF_HOST]

    # Determine device name based on config source
    # If imported from YAML, use the 'name' field; otherwise use 'model'
    if entry.source == SOURCE_IMPORT and CONF_NAME in entry.data:
        device_name = entry.data[CONF_NAME]
    else:
        device_name = entry.data.get(CONF_MODEL, DEFAULT_NAME)

    # Fix stale entity names from previous setup sources
    # When switching between UI (Q450) and YAML (Q350), the entity registry keeps old names
    # Update all comfoconnect entities for this config entry to remove cached names
    # This applies to both SOURCE_USER and SOURCE_IMPORT to handle switching between UI and YAML
    ent_reg = er.async_get(hass)
    for entity in ent_reg.entities.values():
        if entity.config_entry_id == entry.entry_id and entity.platform == DOMAIN:
            # Clear the cached name so HA uses the entity description name instead
            if entity.name:
                _LOGGER.debug(
                    "Clearing stale entity name %s -> %s",
                    entity.entity_id,
                    entity.name,
                )
                ent_reg.async_update_entity(entity.entity_id, name=None)

    bridges = await hass.async_add_executor_job(Bridge.discover, host)
    if not bridges:
        raise ConfigEntryNotReady(f"Could not connect to ComfoConnect bridge on {host}")

    bridge = bridges[0]
    ccb = ComfoConnectBridge(
        hass=hass,
        bridge=bridge,
        name=device_name,
        token=entry.data.get(CONF_TOKEN, DEFAULT_TOKEN),
        friendly_name=entry.data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        pin=entry.data.get(CONF_PIN, DEFAULT_PIN),
    )

    try:
        await hass.async_add_executor_job(ccb.connect)
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Could not connect to ComfoConnect bridge on {host}"
        ) from err

    entry.runtime_data = ccb

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(entry.runtime_data.disconnect)

    return unload_ok


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
