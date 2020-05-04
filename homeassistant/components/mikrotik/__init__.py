"""The Mikrotik component."""
from datetime import timedelta

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

# HOST_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_HOST): cv.string,
#         vol.Required(CONF_USERNAME): cv.string,
#         vol.Required(CONF_PASSWORD): cv.string,
#         vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): cv.port,
#         vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
#     }
# )


# MIKROTIK_SCHEMA = vol.All(
#     vol.Schema(
#         {
#             vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
#             vol.Required(CONF_HUBS): vol.All(cv.ensure_list, [HOST_SCHEMA]),
#             vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
#             vol.Optional(CONF_FORCE_DHCP, default=False): cv.boolean,
#             vol.Optional(
#                 CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME
#             ): cv.time_period,
#         }
#     )
# )

# CONFIG_SCHEMA = vol.Schema(
#     {DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])}, extra=vol.ALLOW_EXTRA
# )


async def async_setup(hass, config):
    """Integration doesn't support configuration through configuration.yaml."""

    # if DOMAIN in config:
    #     for entry in config[DOMAIN]:
    #         hass.async_create_task(
    #             hass.config_entries.flow.async_init(
    #                 DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
    #             )
    #         )

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

    mikrotik = hass.data[DOMAIN].pop(config_entry.entry_id)
    await mikrotik.async_remove_hub_devices()
    for unsub_dispatcher in mikrotik.listeners:
        unsub_dispatcher()

    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")

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
        self.unsub_update = None
        self.listeners = []

    @property
    def signal_data_update(self):
        """Signal data updates."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-data-updated"

    @property
    def signal_update_clients(self):
        """Signal update clients."""
        return f"{DOMAIN}-{self.config_entry.entry_id}-update-clients"

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
            identifiers={(DOMAIN, hub.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=hub.model,
            name=hub.name,
            sw_version=hub.firmware,
        )

    async def async_remove_hub_devices(self):
        """Remove hub devices."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        for hub in self.hubs:
            hub_device = device_registry.async_get_device(
                {(DOMAIN, self.hubs[hub].serial_number)}, set()
            )
            if hub_device:
                device_registry.async_remove_device(hub_device.id)

    # async def async_add_options(self):
    #     """Populate default options for Mikrotik."""
    #     if not self.config_entry.options:
    #         data = dict(self.config_entry.data)
    #         options = {
    #             CONF_ARP_PING: data.pop(CONF_ARP_PING, False),
    #             CONF_FORCE_DHCP: data.pop(CONF_FORCE_DHCP, False),
    #             CONF_DETECTION_TIME: data.pop(
    #                 CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
    #             ),
    #         }

    #         self.hass.config_entries.async_update_entry(
    #             self.config_entry, data=data, options=options
    #         )

    # async def request_update(self):
    #     """Request an update."""
    #     if self.progress is not None:
    #         await self.progress
    #         return

    #     self.progress = self.hass.async_create_task(self.async_update())
    #     await self.progress

    #     self.progress = None

    async def async_update(self):
        """Update clients."""
        for hub in self.hubs:
            await self.hass.async_add_executor_job(self.hubs[hub].update_clients)
        async_dispatcher_send(self.hass, self.signal_data_update)

    async def async_setup(self):
        """Set up a new Mikrotik integration."""

        # await self.async_add_options()

        for hub in self.config_entry.data[CONF_HUBS]:
            new_hub = MikrotikHub(self.hass, self.config_entry, hub, self.clients)
            if await new_hub.async_setup():
                self.hubs[hub] = new_hub
                await self.async_register_device(new_hub)

        if not self.hubs:
            return False

        if not self.available:
            raise ConfigEntryNotReady

        await self.async_update()

        await self.async_set_scan_interval()
        await self.async_set_signal_update_clients()
        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    async def async_set_scan_interval(self):
        """Update scan interval."""

        async def update(event_time):
            """Get the latest data from Mikrotik."""
            await self.async_update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, update, self.option_scan_interval
        )
        self.listeners.append(self.unsub_timer)

    async def async_set_signal_update_clients(self):
        """Update scan interval."""

        async def signal_update(event_time):
            """Get the latest data from Mikrotik."""
            async_dispatcher_send(self.hass, self.signal_update_clients)

        if self.unsub_update is not None:
            self.unsub_update()
        self.unsub_update = async_track_time_interval(
            self.hass, signal_update, self.option_detection_time
        )
        self.listeners.append(self.unsub_update)

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        await hass.data[DOMAIN][entry.entry_id].async_set_scan_interval()
        await hass.data[DOMAIN][entry.entry_id].async_set_signal_update_clients()

    def restore_client(self, mac):
        """Restore a missing device after restart."""
        self.clients[mac] = MikrotikClient(mac, {}, None)
