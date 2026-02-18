"""Support for Ness D8X/D16X devices."""

from __future__ import annotations

import logging
from typing import NamedTuple

from nessclient import ArmingMode, ArmingState, Client
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INFER_ARMING_STATE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    PLATFORMS,
    SIGNAL_ARMING_STATE_CHANGED,
    SIGNAL_ZONE_CHANGED,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

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
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.positive_time_period,
                vol.Optional(CONF_ZONES, default=[]): vol.All(
                    cv.ensure_list, [ZONE_SCHEMA]
                ),
                vol.Optional(CONF_INFER_ARMING_STATE, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ness Alarm platform."""
    async_setup_services(hass)

    if DOMAIN in config:
        # Only import if no config entries exist yet
        if not hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data=config[DOMAIN],
                )
            )

        # Notify user that YAML config is deprecated
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2026.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Ness Alarm",
            },
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NessAlarmConfigEntry) -> bool:
    """Set up Ness Alarm from a config entry."""
    client = Client(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        update_interval=DEFAULT_SCAN_INTERVAL.total_seconds(),
        infer_arming_state=entry.data.get(CONF_INFER_ARMING_STATE, False),
    )

    # Verify the client can connect to the alarm panel
    try:
        await client.update()
    except OSError as err:
        await client.close()
        raise ConfigEntryNotReady(
            f"Unable to connect to alarm panel at"
            f" {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        ) from err

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

    async def _close(event: Event) -> None:
        await client.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    async def _started(hass: HomeAssistant) -> None:
        _LOGGER.debug("Invoking client keepalive() & update()")
        hass.async_create_task(client.keepalive())
        hass.async_create_task(client.update())

    async_at_started(hass, _started)

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
