"""The AV Receiver integration."""
from pyavreceiver import const as avr_const, factory
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ZONE1,
    CONF_ZONE2,
    CONF_ZONE3,
    CONF_ZONE4,
    CONTROLLER,
    DOMAIN,
    SIGNAL_AVR_UPDATED,
    UNSUB_UPDATE_LISTENER,
    ZONES,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string})}, extra=vol.ALLOW_EXTRA
)

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

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up AV Receiver from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    controller = None
    try:
        controller = await factory(host)
        await controller.init()
        entry.unique_id = (
            f"{DOMAIN}-{controller.serial_number or controller.mac or controller.host}"
        )
    except Exception as error:
        if controller:
            await controller.disconnect()
        raise ConfigEntryNotReady from error

    # Disconnect when shutting down
    async def disconnect_avreceiver(event):
        await controller.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_avreceiver)

    controller_manager = AVRManager(hass, controller)
    await controller_manager.connect_listeners()

    unsub = entry.add_update_listener(update_listener)

    zones = [
        CONF_ZONE1,
        CONF_ZONE2 if entry.options.get(CONF_ZONE2) else "",
        CONF_ZONE2 if entry.options.get(CONF_ZONE3) else "",
        CONF_ZONE2 if entry.options.get(CONF_ZONE4) else "",
    ]
    zones = {
        name: getattr(controller, name)
        for name in zones
        if getattr(controller, name, None)
    }

    hass.data[DOMAIN][entry.entry_id] = {
        CONTROLLER: controller_manager,
        MEDIA_PLAYER_DOMAIN: zones,
        UNSUB_UPDATE_LISTENER: unsub,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.data[DOMAIN][entry.entry_id][CONTROLLER].disconnect()

    hass.data[DOMAIN][entry.entry_id][UNSUB_UPDATE_LISTENER]()

    entity_registry = await er.async_get_registry(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    zone_names = [CONF_ZONE1, CONF_ZONE2, CONF_ZONE3, CONF_ZONE4]
    for zone in entries:
        for name in zone_names:
            if zone.unique_id == f"{entry.unique_id}-{name}":
                entity_registry.async_remove(zone.entity_id)

    hass.data[DOMAIN].pop(entry.entry_id)

    return await hass.config_entries.async_forward_entry_unload(
        entry, MEDIA_PLAYER_DOMAIN
    )


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class AVRManager:
    """Class the manages events of the AV Receiver."""

    def __init__(self, hass, avreceiver):
        """Init the manager."""
        self._hass = hass
        self.avreceiver = avreceiver
        self._signals = []

    async def connect_listeners(self):
        """Subscribe to events."""
        # Handle AVR state update events
        self._signals.append(
            self.avreceiver.dispatcher.connect(
                avr_const.SIGNAL_STATE_UPDATE, self._state_update
            )
        )
        # Handle connection-related events
        self._signals.append(
            self.avreceiver.dispatcher.connect(
                avr_const.SIGNAL_TELNET_EVENT, self._connection_update
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

    async def _connection_update(self, event):
        """Handle controller connection event."""
        # Update state when receiver recovers from connection failure
        if event == avr_const.EVENT_CONNECTED:
            for zone_name in ZONES:
                if zone := getattr(self.avreceiver, zone_name, None):
                    await zone.update_all()
        self._hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_AVR_UPDATED)
