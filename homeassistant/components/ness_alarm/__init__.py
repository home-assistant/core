"""Support for Ness D8X/D16X devices."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import NamedTuple

from nessclient import ArmingMode, ArmingState, Client
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_STATE,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_OUTPUT_ID,
    CONF_INFER_ARMING_STATE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    PLATFORMS,
    SERVICE_AUX,
    SERVICE_PANIC,
    SIGNAL_ARMING_STATE_CHANGED,
    SIGNAL_ZONE_CHANGED,
    SUBENTRY_TYPE_HOME,
)

_LOGGER = logging.getLogger(__name__)

DATA_NESS: HassKey[Client] = HassKey(DOMAIN)

type NessAlarmConfigEntry = ConfigEntry[Client]


class ZoneChangedData(NamedTuple):
    """Data for a zone state change."""

    zone_id: int
    state: bool


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_NAME): cv.string,
        vol.Required(CONF_ZONE_ID): cv.positive_int,
        vol.Optional(
            CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE
        ): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    }
)

# YAML configuration is deprecated but supported for import
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_INFER_ARMING_STATE, default=False): cv.boolean,
                vol.Optional(CONF_ZONES, default=[]): vol.All(
                    cv.ensure_list, [ZONE_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_PANIC = vol.Schema({vol.Required(ATTR_CODE): cv.string})
SERVICE_SCHEMA_AUX = vol.Schema(
    {
        vol.Required(ATTR_OUTPUT_ID): cv.positive_int,
        vol.Optional(ATTR_STATE, default=True): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: NessAlarmConfigEntry) -> bool:
    """Set up Ness Alarm from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    infer_arming_state = entry.data.get(CONF_INFER_ARMING_STATE, False)

    # Use constant scan interval (not user-configurable per HA guidelines)
    scan_interval = DEFAULT_SCAN_INTERVAL

    client = Client(
        host=host,
        port=port,
        update_interval=scan_interval.total_seconds(),
        infer_arming_state=infer_arming_state,
    )

    # Store in runtime_data
    entry.runtime_data = client

    def on_zone_change(zone_id: int, state: bool) -> None:
        """Receive and propagate zone state updates."""
        async_dispatcher_send(
            hass, SIGNAL_ZONE_CHANGED, ZoneChangedData(zone_id=zone_id, state=state)
        )

    def on_state_change(
        arming_state: ArmingState, arming_mode: ArmingMode | None
    ) -> None:
        """Receive and propagate arming state updates."""
        async_dispatcher_send(
            hass, SIGNAL_ARMING_STATE_CHANGED, arming_state, arming_mode
        )

    client.on_zone_change(on_zone_change)
    client.on_state_change(on_state_change)

    async def _close(event):
        await client.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    async def _started(event):
        _LOGGER.debug("Invoking client keepalive() & update()")
        hass.async_create_task(client.keepalive())
        hass.async_create_task(client.update())

    async_at_started(hass, _started)

    # Ensure a "Home" subentry exists for the alarm panel
    home_subentry_exists = any(
        subentry.subentry_type == SUBENTRY_TYPE_HOME
        for subentry in entry.subentries.values()
    )

    if not home_subentry_exists:
        home_subentry = ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_HOME,
            subentry_id="home_subentry",
            unique_id=f"{SUBENTRY_TYPE_HOME}_main",
            title="Home",
            data=MappingProxyType({}),
        )
        hass.config_entries.async_add_subentry(entry, home_subentry)

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (check if already registered to avoid duplicates)
    async_setup_services(hass, client)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NessAlarmConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def async_setup_services(hass: HomeAssistant, client: Client) -> None:
    """Register services."""

    async def handle_panic(call: ServiceCall) -> None:
        await client.panic(call.data[ATTR_CODE])

    async def handle_aux(call: ServiceCall) -> None:
        await client.aux(call.data[ATTR_OUTPUT_ID], call.data[ATTR_STATE])

    # Only register services if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_PANIC):
        hass.services.async_register(
            DOMAIN, SERVICE_PANIC, handle_panic, schema=SERVICE_SCHEMA_PANIC
        )
    if not hass.services.has_service(DOMAIN, SERVICE_AUX):
        hass.services.async_register(
            DOMAIN, SERVICE_AUX, handle_aux, schema=SERVICE_SCHEMA_AUX
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ness Alarm platform."""
    if DOMAIN in config:
        # YAML configuration exists - trigger import flow
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=config[DOMAIN],
            )
        )
    return True
