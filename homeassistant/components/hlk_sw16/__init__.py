"""Support for HLK-SW16 relay switches."""

import asyncio
import logging
from typing import Any

from hlk_sw16 import create_hlk_sw16_connection
from hlk_sw16.protocol import SW16Client
import probatio

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SWITCHES, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    INTEGRATION_TITLE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]

SWITCH_SCHEMA = probatio.Schema({probatio.Optional(CONF_NAME): cv.string})

RELAY_ID = probatio.All(
    probatio.Any(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c", "d", "e", "f"),
    probatio.Coerce(str),
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                cv.string: probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): cv.string,
                        probatio.Optional(
                            CONF_PORT, default=DEFAULT_PORT
                        ): probatio.Port(),
                        probatio.Required(CONF_SWITCHES): probatio.Schema(
                            {RELAY_ID: SWITCH_SCHEMA}
                        ),
                    }
                )
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

type HlkConfigEntry = ConfigEntry[SW16Client]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Component setup, do nothing."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        _async_import_yaml(
            hass,
            [
                {CONF_HOST: conf[CONF_HOST], CONF_PORT: conf[CONF_PORT]}
                for conf in config[DOMAIN].values()
            ],
        )
    )
    return True


async def _async_import_yaml(
    hass: HomeAssistant, import_data: list[dict[str, Any]]
) -> None:
    """Import the YAML devices into config entries."""
    # Eager tasks register the import flows before setup waits for them.
    results = await asyncio.gather(
        *(
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=data
                )
            )
            for data in import_data
        )
    )
    failed_reasons = {
        result["reason"]
        for result in results
        if result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    }
    for reason in failed_reasons:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
    # The shared issue tells users to remove all YAML, which would drop failed devices.
    if failed_reasons:
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: HlkConfigEntry) -> None:
    """Set up the HLK-SW16 switch."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    address = f"{host}:{port}"

    @callback
    def disconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s disconnected", address)
        async_dispatcher_send(
            hass, f"hlk_sw16_device_available_{entry.entry_id}", False
        )

    @callback
    def reconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s connected", address)
        async_dispatcher_send(hass, f"hlk_sw16_device_available_{entry.entry_id}", True)

    _LOGGER.debug("Initiating HLK-SW16 connection to %s", address)

    client = await create_hlk_sw16_connection(
        host=host,
        port=port,
        disconnect_callback=disconnected,
        reconnect_callback=reconnected,
        loop=hass.loop,
        timeout=CONNECTION_TIMEOUT,
        reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
        keep_alive_interval=DEFAULT_KEEP_ALIVE_INTERVAL,
    )

    entry.runtime_data = client

    # Load entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Connected to HLK-SW16 device: %s", address)


async def async_unload_entry(hass: HomeAssistant, entry: HlkConfigEntry) -> None:
    """Unload a config entry."""
    entry.runtime_data.stop()
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
