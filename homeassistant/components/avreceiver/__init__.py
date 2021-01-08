"""The AV Receiver integration."""
import asyncio

import pyavreceiver
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import format_title
from .const import DOMAIN, SIGNAL_AVR_UPDATED

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = [MEDIA_PLAYER_DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the AV Receiver component."""
    if DOMAIN not in config:
        return True
    host = config[DOMAIN][CONF_HOST]
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        # Create new entry based on config
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data={CONF_HOST: host}
            )
        )
    else:
        # Check if host needs to be updated
        entry = entries[0]
        if entry.data[CONF_HOST] != host:
            hass.config_entries.async_update_entry(
                entry, title=format_title(host), data={**entry.data, CONF_HOST: host}
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up AV Receiver from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    host = entry.data[CONF_HOST]
    try:
        controller = await pyavreceiver.factory(host)
        await controller.init()
    except Exception as error:
        raise ConfigEntryNotReady from error

    # Disconnect when shutting down
    async def disconnect_avreceiver(event):
        await controller.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_avreceiver)

    controller_manager = AVRManager(hass, controller)
    await controller_manager.connect_listeners()

    zones = ["main", "zone2", "zone3", "zone4"]
    zones = {
        name: getattr(controller, name) for name in zones if getattr(controller, name)
    }

    hass.data[DOMAIN][entry.entry_id] = {
        "controller": controller_manager,
        MEDIA_PLAYER_DOMAIN: zones,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    controller_manager = hass.data[DOMAIN][entry.entry_id]["controller"]
    await controller_manager.disconnect()
    hass.data.pop(DOMAIN)

    return await hass.config_entries.async_forward_entry_unload(
        entry, MEDIA_PLAYER_DOMAIN
    )


class AVRManager:
    """Class the manages events of the AV Receiver."""

    def __init__(self, hass, avreceiver):
        """Init the manager."""
        self._hass = hass
        self._device_registry = None
        self._entity_registry = None
        self.avreceiver = avreceiver
        self._signals = []

    async def connect_listeners(self):
        """Subscribe to events."""
        self._device_registry, self._entity_registry = await asyncio.gather(
            self._hass.helpers.device_registry.async_get_registry(),
            self._hass.helpers.entity_registry.async_get_registry(),
        )
        # Handle AVR state update events
        self._signals.append(
            self.avreceiver.dispatcher.connect(
                pyavreceiver.const.SIGNAL_STATE_UPDATE, self._state_update
            )
        )
        # Handle connection-related events
        self._signals.append(
            self.avreceiver.dispatcher.connect(
                pyavreceiver.const.SIGNAL_TELNET_EVENT, self._telnet_event
            )
        )

    async def disconnect(self):
        """Disconnect subscriptions."""
        for signal_remove in self._signals:
            signal_remove()
        self._signals.clear()
        self.avreceiver.dispatcher.disconnect_all()
        await self.avreceiver.disconnect()

    async def _state_update(self, event):
        """Handle controller event."""
        self._hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_AVR_UPDATED)

    async def _telnet_event(self, event):
        """Handle connection event."""
        self._hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_AVR_UPDATED)
