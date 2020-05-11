"""The Mikrotik component."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_MANUFACTURER,
    CONF_DETECTION_TIME,
    CONF_HUBS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .hub import MikrotikClient, MikrotikHub

CONFIG_SCHEMA = vol.Schema(
    cv.deprecated(DOMAIN, invalidation_version="0.110"), {DOMAIN: cv.match_all},
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Integration doesn't support configuration through configuration.yaml."""

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Mikrotik component."""

    # migrate old config_entry to new structure
    if CONF_HUBS not in config_entry.data:
        old_config_entry = dict(config_entry.data)
        new_config_entry_data = {}
        new_config_entry_data[CONF_NAME] = old_config_entry.pop(CONF_NAME)
        new_config_entry_data.setdefault(CONF_HUBS, {})[
            old_config_entry[CONF_HOST]
        ] = old_config_entry
        hass.config_entries.async_update_entry(config_entry, data=new_config_entry_data)

    mikrotik = Mikrotik(hass, config_entry)
    if not await mikrotik.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = mikrotik

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "device_tracker")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")

    mikrotik = hass.data[DOMAIN].pop(config_entry.entry_id)
    await mikrotik.async_cleanup()

    return True


class Mikrotik:
    """Represent Mikrotik Integration."""

    def __init__(self, hass, config_entry):
        """Initialize Mikrotik Integration."""
        self.hass = hass
        self.config_entry = config_entry
        self.hubs = {}
        self.clients = {}
        self.unsub_timer = None
        self.unsub_listener = None

    @property
    def signal_data_update(self):
        """Signal data updates."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-data-updated"

    @property
    def signal_new_clients(self):
        """Signal update clients."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-new-clients"

    @property
    def signal_options_update(self):
        """Signal options updated."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-options-updated"

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def option_scan_interval(self):
        """Config entry option defining interval to updating clients."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
        )

    @property
    def available(self):
        """Return avaiabilty based on hub status."""
        for hub in self.hubs:
            if self.hubs[hub].available:
                return True
        return False

    async def async_register_device(self, hub):
        """Register new hub device."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, hub.host)},
            manufacturer=ATTR_MANUFACTURER,
            model=hub.model,
            name=hub.name,
            sw_version=hub.firmware,
        )

    async def async_update(self):
        """Update clients."""
        len_old_clients = len(self.clients)
        for hub in self.hubs:
            await self.hass.async_add_executor_job(self.hubs[hub].update_clients)

        if len_old_clients != len(self.clients):
            _LOGGER.debug("New clients detected")
            async_dispatcher_send(self.hass, self.signal_new_clients)

        async_dispatcher_send(self.hass, self.signal_data_update)

    async def async_setup(self):
        """Set up a new Mikrotik integration."""

        await self.async_get_clients_from_registry()

        for hub in self.config_entry.data[CONF_HUBS]:
            new_hub = MikrotikHub(self.hass, self.config_entry, hub, self.clients)
            if await new_hub.async_setup():
                self.hubs[hub] = new_hub
                await self.async_register_device(new_hub)

        if not self.hubs:
            return False

        if not self.available:
            raise ConfigEntryNotReady

        await self.async_set_update_interval()
        # run update twice only during setup to update clients from all hubs
        await self.async_update()
        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    async def async_get_clients_from_registry(self):
        """Get list of clients from entity registry."""
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entities = self.hass.helpers.entity_registry.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        if entities:
            self.clients = {
                entity.unique_id: MikrotikClient(entity.unique_id)
                for entity in entities
            }

    async def async_cleanup(self):
        """Remove update signals."""
        # pylint: disable=not-callable
        if self.unsub_timer:
            self.unsub_timer()

        if self.unsub_listener:
            self.unsub_listener()

    async def async_set_update_interval(self):
        """Update scan interval."""

        async def async_update_data(event_time=None):
            """Get the latest data from Mikrotik."""
            await self.async_update()

        if self.unsub_timer:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, async_update_data, self.option_scan_interval
        )
        await async_update_data()

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        await hass.data[DOMAIN][entry.entry_id].async_set_update_interval()
