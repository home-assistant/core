"""Code to handle the api connection to a Roon server."""
import logging
from homeassistant.const import CONF_HOST, CONF_API_KEY
from homeassistant.util.dt import utcnow
from homeassistant.core import callback
from asyncio import ensure_future, sleep, run_coroutine_threadsafe
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (DOMAIN, CONF_CUSTOM_PLAY_ACTION, ROON_APPINFO)

_LOGGER = logging.getLogger(__name__)
FULL_SYNC_INTERVAL = 30

class RoonServer:
    """Manages a single Roon Server."""

    def __init__(self, hass, config_entry, custom_play_action):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.roonapi = None
        self.all_player_ids = []
        self.all_playlists = []
        self.offline_devices = []
        self.custom_play_action = custom_play_action


    @property
    def host(self):
        """Return the host of this server."""
        return self.config_entry.data[CONF_HOST]

    async def async_setup(self, tries=0):
        """Set up a roon server based on host parameter."""
        host = self.host
        hass = self.hass
        token = self.config_entry.data[CONF_API_KEY]
        from roon import RoonApi
        self.roonapi = RoonApi(ROON_APPINFO, token, host, blocking_init=False)
        self.roonapi.register_state_callback(self.roonapi_state_callback, event_filter=["zones_changed"])

        # initialize media_player platform
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(self.config_entry, 'media_player'))

        # Initialize Roon background polling
        ensure_future(self.async_do_loop())

        return True

    async def async_reset(self):
        """Reset this connection to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        self.stop_roon()
        return True

    @property
    def zones(self):
        return self.roonapi.zones
        
    def stop_roon(self):
        '''Stop background worker'''
        self.roonapi.stop()
        self._exit = True

    def roonapi_state_callback(self, event, changed_zones):
        '''callbacks from the roon api websockets'''
        run_coroutine_threadsafe(self.async_update_changed_players(changed_zones), self.hass.loop)

    async def async_do_loop(self):
        ''' background work loop'''
        self._exit = False
        while not self._exit:
            await self.async_update_players()
            #await self.async_update_playlists()
            await sleep(FULL_SYNC_INTERVAL, self.hass.loop)

    async def async_update_changed_players(self, changed_zones_ids):
        """Update the players which were reported as changed by the Roon API"""
        for zone_id in changed_zones_ids:
            if zone_id not in self.roonapi.zones:
                # device was removed ?
                continue
            zone = self.roonapi.zones[zone_id]
            for device in zone["outputs"]:
                dev_name = device['display_name']
                if dev_name == "Unnamed" or not dev_name:
                    # ignore unnamed devices
                    continue
                player_data = await self.async_create_player_data(zone, device)
                dev_id = player_data["dev_id"]
                player_data["is_available"] = True
                if dev_id in self.offline_devices:
                    # player back online
                    self.offline_devices.remove(dev_id)
                async_dispatcher_send(self.hass, 'roon_media_player', player_data)
                if not dev_id in self.all_player_ids:
                    self.all_player_ids.append(dev_id)

    async def async_update_players(self):
        ''' periodic full scan of all devices'''
        zone_ids = self.roonapi.zones.keys()
        await self.async_update_changed_players(zone_ids)
        # check for any removed devices
        all_devs = {}
        for zone_id in zone_ids:
            zone = self.roonapi.zones[zone_id]
            for device in zone["outputs"]:
                player_data = await self.async_create_player_data(zone, device)
                dev_id = player_data["dev_id"]
                all_devs[dev_id] = player_data
        for dev_id in self.all_player_ids:
            if dev_id not in all_devs.keys():
                # player was removed!
                player_data = {'dev_id': dev_id}
                player_data["is_available"] = False
                async_dispatcher_send(self.hass, 'roon_media_player', player_data)
                self.offline_devices.append(dev_id)
     
    async def async_update_playlists(self):
        ''' store lists in memory with all playlists - acessible by custom lovelace card later '''

        # TODO: work out how to use this data in a custom UI component
        all_playlists = []
        roon_playlists = self.roonapi.playlists()
        if roon_playlists and "items" in roon_playlists:
            all_playlists += [item["title"] for item in roon_playlists["items"]]
        roon_playlists = self.roonapi.internet_radio()
        if roon_playlists and "items" in roon_playlists:
            all_playlists += [item["title"] for item in roon_playlists["items"]]
        self.all_playlists = all_playlists

    async def async_create_player_data(self, zone, output):
        ''' create player object dict by combining zone with output'''
        new_dict = zone.copy()
        new_dict.update(output)
        new_dict.pop("outputs")
        new_dict["host"] = self.host
        new_dict["is_synced"] = len(zone["outputs"]) > 1
        new_dict["zone_name"] = zone["display_name"]
        new_dict["display_name"] = output["display_name"]
        new_dict["last_changed"] = utcnow()
        # we don't use the zone_id or output_id for now as unique id as I've seen cases were it changes for some reason
        new_dict["dev_id"] = "roon_%s_%s" % (self.host, output["display_name"])
        return new_dict

