"""Support for Ness D8X/D16X alarm panel."""

from __future__ import annotations

import logging

from nessclient import ArmingMode, ArmingState, Client
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ID,
    CONF_INFER_ARMING_STATE,
    CONF_NAME,
    CONF_SUPPORT_HOME_ARM,
    CONF_TYPE,
    CONF_ZONES,
    DEFAULT_INFER_ARMING_STATE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUPPORT_HOME_ARM,
    DOMAIN,
    SERVICE_AUX,
    SERVICE_CODE,
    SERVICE_PANIC,
)

_LOGGER = logging.getLogger(__name__)

SIGNAL_ZONE_CHANGED = f"{DOMAIN}_zone_changed"
SIGNAL_ARMING_STATE_CHANGED = f"{DOMAIN}_arming_state_changed"

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE): cv.string,
    }
)

PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(
                    CONF_INFER_ARMING_STATE, default=DEFAULT_INFER_ARMING_STATE
                ): cv.boolean,
                vol.Optional(CONF_ZONES, default=[]): vol.All(
                    cv.ensure_list, [ZONE_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ness Alarm component from YAML configuration."""
    if DOMAIN not in config:
        return True

    yaml_config = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=yaml_config,
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ness Alarm from a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    infer_arming_state = entry.options.get(
        CONF_INFER_ARMING_STATE,
        entry.data.get(CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE),
    )

    support_home_arm = entry.options.get(
        CONF_SUPPORT_HOME_ARM,
        entry.data.get(CONF_SUPPORT_HOME_ARM, DEFAULT_SUPPORT_HOME_ARM),
    )

    client = Client(
        host=host,
        port=port,
        update_interval=scan_interval,
        infer_arming_state=infer_arming_state,
    )

    @callback
    def on_zone_change(zone_id: int, state: bool) -> None:
        """Handle zone state changes."""
        async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, zone_id, state)

    def on_state_change(arming_state: ArmingState, arming_mode: ArmingMode | None):
        """Receives and propagates arming state updates."""
        async_dispatcher_send(
            hass, SIGNAL_ARMING_STATE_CHANGED, arming_state, arming_mode
        )

    client.on_zone_change(on_zone_change)
    client.on_state_change(on_state_change)

    entry.runtime_data = {
        "client": client,
        "config": {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_INFER_ARMING_STATE: infer_arming_state,
            CONF_SUPPORT_HOME_ARM: support_home_arm,
            CONF_ZONES: entry.data.get(CONF_ZONES, []),
        },
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_shutdown(event) -> None:
        """Handle Home Assistant shutdown."""
        await client.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_shutdown)
    )

    async def _started(event):
        _LOGGER.debug("invoking client keepalive() & update()")
        hass.loop.create_task(client.keepalive())
        hass.loop.create_task(client.update())

    async_at_started(hass, _started)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = entry.runtime_data
        await data["client"].close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Ness Alarm."""

    if hass.services.has_service(DOMAIN, SERVICE_AUX):
        return

    async def handle_aux(call: ServiceCall) -> None:
        """Handle aux service call."""
        output_id = call.data.get("output_id")
        state = call.data.get("state", True)

        for entry in hass.config_entries.async_entries(DOMAIN):
            client = entry.runtime_data.get("client") if entry.runtime_data else None
            if client:
                await client.aux(output_id, state)
                break

    async def handle_panic(call: ServiceCall) -> None:
        """Handle panic service call."""
        code = call.data.get(SERVICE_CODE)

        for entry in hass.config_entries.async_entries(DOMAIN):
            client = entry.runtime_data.get("client") if entry.runtime_data else None
            if client:
                await client.panic(code)
                break

    hass.services.async_register(
        DOMAIN,
        SERVICE_AUX,
        handle_aux,
        schema=vol.Schema(
            {
                vol.Required("output_id"): cv.positive_int,
                vol.Required("state", default=True): cv.boolean,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PANIC,
        handle_panic,
        schema=vol.Schema(
            {
                vol.Optional(SERVICE_CODE): cv.string,
            }
        ),
    )
