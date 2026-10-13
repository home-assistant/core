"""Support for Ness D8X/D16X devices."""

import logging
from typing import NamedTuple

from nessclient import ArmingMode, ArmingState, Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INFER_ARMING_STATE,
    DEFAULT_SCAN_INTERVAL,
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


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ness Alarm platform."""
    async_setup_services(hass)

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
