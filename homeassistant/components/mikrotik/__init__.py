"""The Mikrotik component."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_MANUFACTURER,
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    CONF_HUBS,
    DEFAULT_API_PORT,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DOMAIN,
)
from .hub import MikrotikClient, MikrotikHub

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): cv.port,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    }
)


MIKROTIK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(CONF_HUBS): vol.All(cv.ensure_list, [HOST_SCHEMA]),
            vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
            vol.Optional(CONF_FORCE_DHCP, default=False): cv.boolean,
            vol.Optional(
                CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME
            ): cv.time_period,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Import the Mikrotik component from config."""

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Mikrotik component."""

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
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True


class Mikrotik:
    """Represent Mikrotik Integration."""

    def __init__(self, hass, config_entry):
        """Initialize Mikrotik Integration."""
        self.hass = hass
        self.config_entry = config_entry
        self.hubs = {}
        self.clients = {}
        self.progress = None

    @property
    def signal_update(self):
        """Signal data updates."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-data-updated"

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(seconds=self.config_entry.options[CONF_DETECTION_TIME])

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
        device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, hub.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=hub.model,
            name=hub.name,
            sw_version=hub.firmware,
        )
        return device.id

    async def async_add_options(self):
        """Populate default options for Mikrotik."""
        if not self.config_entry.options:
            data = dict(self.config_entry.data)
            options = {
                CONF_ARP_PING: data.pop(CONF_ARP_PING, False),
                CONF_FORCE_DHCP: data.pop(CONF_FORCE_DHCP, False),
                CONF_DETECTION_TIME: data.pop(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                ),
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options=options
            )

    async def request_update(self):
        """Request an update."""
        if self.progress is not None:
            await self.progress
            return

        self.progress = self.hass.async_create_task(self.async_update())
        await self.progress

        self.progress = None

    async def async_update(self):
        """Update clients."""
        for hub in self.hubs:
            await self.hass.async_add_executor_job(self.hubs[hub].update_clients)
        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up a new Mikrotik integration."""

        # migrate old config_entry to new structure
        if self.config_entry.data and CONF_HUBS not in self.config_entry.data:
            old_config_entry = dict(self.config_entry.data)
            new_config_entry_data = {}
            new_config_entry_data[CONF_NAME] = old_config_entry.pop(CONF_NAME)
            new_config_entry_data.setdefault(CONF_HUBS, {})[
                old_config_entry[CONF_HOST]
            ] = old_config_entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_config_entry_data
            )

        await self.async_add_options()

        config_entry_ready = False
        for hub in self.config_entry.data[CONF_HUBS]:
            new_hub = MikrotikHub(self.hass, self.config_entry, hub, self.clients)
            if await new_hub.async_setup():
                self.hubs[hub] = new_hub
                if new_hub.available:
                    await self.async_register_device(new_hub)
                    config_entry_ready = True

        if not config_entry_ready:
            raise ConfigEntryNotReady

        if not self.hubs:
            return False

        await self.async_update()
        return True

    def restore_client(self, mac):
        """Restore a missing device after restart."""
        self.clients[mac] = MikrotikClient(mac, {}, None)
