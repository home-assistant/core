"""Code to handle the api connection to a Roon server."""
import asyncio
import logging

from roonapi import RoonApi

from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.dt import utcnow

from .const import CONF_ROON_ID, ROON_APPINFO

_LOGGER = logging.getLogger(__name__)
FULL_SYNC_INTERVAL = 30


class RoonServer:
    """Manages a single Roon Server."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.roonapi = None
        self.roon_id = None
        self.all_player_ids = set()
        self.all_playlists = []
        self.offline_devices = set()
        self._exit = False
        self._roon_name_by_id = {}
        self._id_by_roon_name = {}

    async def async_setup(self, tries=0):
        """Set up a roon server based on config parameters."""
        hass = self.hass
        # Host will be None for configs using discovery
        host = self.config_entry.data[CONF_HOST]
        token = self.config_entry.data[CONF_API_KEY]
        # Default to None for compatibility with older configs
        core_id = self.config_entry.data.get(CONF_ROON_ID)
        _LOGGER.debug("async_setup: host=%s core_id=%s token=%s", host, core_id, token)

        self.roonapi = RoonApi(
            ROON_APPINFO, token, host, blocking_init=False, core_id=core_id
        )
        self.roonapi.register_state_callback(
            self.roonapi_state_callback, event_filter=["zones_changed"]
        )

        # Default to 'host' for compatibility with older configs without core_id
        self.roon_id = core_id if core_id is not None else host

        # initialize media_player platform
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                self.config_entry, "media_player"
            )
        )

        # Initialize Roon background polling
        asyncio.create_task(self.async_do_loop())

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
        """Return list of zones."""
        return self.roonapi.zones

    def add_player_id(self, entity_id, roon_name):
        """Register a roon player."""
        self._roon_name_by_id[entity_id] = roon_name
        self._id_by_roon_name[roon_name] = entity_id

    def roon_name(self, entity_id):
        """Get the name of the roon player from entity_id."""
        return self._roon_name_by_id.get(entity_id)

    def entity_id(self, roon_name):
        """Get the id of the roon player from the roon name."""
        return self._id_by_roon_name.get(roon_name)

    def stop_roon(self):
        """Stop background worker."""
        self.roonapi.stop()
        self._exit = True

    def roonapi_state_callback(self, event, changed_zones):
        """Callbacks from the roon api websockets."""
        self.hass.add_job(self.async_update_changed_players(changed_zones))

    async def async_do_loop(self):
        """Background work loop."""
        self._exit = False
        while not self._exit:
            await self.async_update_players()
            # await self.async_update_playlists()
            await asyncio.sleep(FULL_SYNC_INTERVAL)

    async def async_update_changed_players(self, changed_zones_ids):
        """Update the players which were reported as changed by the Roon API."""
        for zone_id in changed_zones_ids:
            if zone_id not in self.roonapi.zones:
                # device was removed ?
                continue
            zone = self.roonapi.zones[zone_id]
            for device in zone["outputs"]:
                dev_name = device["display_name"]
                if dev_name == "Unnamed" or not dev_name:
                    # ignore unnamed devices
                    continue
                player_data = await self.async_create_player_data(zone, device)
                dev_id = player_data["dev_id"]
                player_data["is_available"] = True
                if dev_id in self.offline_devices:
                    # player back online
                    self.offline_devices.remove(dev_id)
                async_dispatcher_send(self.hass, "roon_media_player", player_data)
                self.all_player_ids.add(dev_id)

    async def async_update_players(self):
        """Periodic full scan of all devices."""
        zone_ids = self.roonapi.zones.keys()
        await self.async_update_changed_players(zone_ids)
        # check for any removed devices
        all_devs = {}
        for zone in self.roonapi.zones.values():
            for device in zone["outputs"]:
                player_data = await self.async_create_player_data(zone, device)
                dev_id = player_data["dev_id"]
                all_devs[dev_id] = player_data
        for dev_id in self.all_player_ids:
            if dev_id in all_devs:
                continue
            # player was removed!
            player_data = {"dev_id": dev_id}
            player_data["is_available"] = False
            async_dispatcher_send(self.hass, "roon_media_player", player_data)
            self.offline_devices.add(dev_id)

    async def async_create_player_data(self, zone, output):
        """Create player object dict by combining zone with output."""
        new_dict = zone.copy()
        new_dict.update(output)
        new_dict.pop("outputs")
        new_dict["roon_id"] = self.roon_id
        new_dict["is_synced"] = len(zone["outputs"]) > 1
        new_dict["zone_name"] = zone["display_name"]
        new_dict["display_name"] = output["display_name"]
        new_dict["last_changed"] = utcnow()
        # we don't use the zone_id or output_id for now as unique id as I've seen cases were it changes for some reason
        new_dict["dev_id"] = f"roon_{self.roon_id}_{output['display_name']}"
        return new_dict
