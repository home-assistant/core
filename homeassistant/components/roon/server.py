"""Code to handle the api connection to a Roon server."""
import asyncio
import logging

from roonapi import RoonApi, RoonDiscovery

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ENABLE_VOLUME_HOOKS,
    CONF_ROON_ID,
    ROON_APPINFO,
    ROON_EVENT,
    ROON_EVENT_VOLUME_DOWN,
    ROON_EVENT_VOLUME_UP,
)

_LOGGER = logging.getLogger(__name__)
INITIAL_SYNC_INTERVAL = 5
FULL_SYNC_INTERVAL = 30


class RoonServer:
    """Manages a single Roon Server."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.roonapi = None
        self.roon_id = None
        self.volume_hook = False
        self.all_player_ids = set()
        self.all_playlists = []
        self.offline_devices = set()
        self._exit = False
        self._roon_name_by_id = {}
        self._id_by_roon_name = {}

        config_entry.async_on_unload(
            config_entry.add_update_listener(self.update_listener)
        )

    async def async_setup(self, tries=0):
        """Set up a roon server based on config parameters."""

        def get_roon_host():
            host = self.config_entry.data.get(CONF_HOST)
            port = self.config_entry.data.get(CONF_PORT)
            if host:
                _LOGGER.debug("static roon core host=%s port=%s", host, port)
                return (host, port)

            discover = RoonDiscovery(core_id)
            server = discover.first()
            discover.stop()
            _LOGGER.debug("dynamic roon core core_id=%s server=%s", core_id, server)
            return (server[0], server[1])

        def get_roon_api():
            token = self.config_entry.data[CONF_API_KEY]
            (host, port) = get_roon_host()
            return RoonApi(ROON_APPINFO, token, host, port, blocking_init=True)

        core_id = self.config_entry.data.get(CONF_ROON_ID)

        self.volume_hook = self.config_entry.options.get(
            CONF_ENABLE_VOLUME_HOOKS, False
        )
        _LOGGER.error("Volume_hook=%s", self.volume_hook)

        self.roonapi = await self.hass.async_add_executor_job(get_roon_api)

        self.roonapi.register_state_callback(
            self.roonapi_state_callback, event_filter=["zones_changed"]
        )

        # Default to 'host' for compatibility with older configs without core_id
        self.roon_id = (
            core_id if core_id is not None else self.config_entry.data[CONF_HOST]
        )

        # Initialize Roon background polling
        self.config_entry.async_create_background_task(
            self.hass, self.async_do_loop(), "roon.server-do-loop"
        )

        return True

    async def async_reset(self):
        """Reset this connection to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        self.stop_roon()
        return True

    async def update_listener(self, hass, config_entry):
        """Handle options update."""
        volume_hook = self.config_entry.options.get(CONF_ENABLE_VOLUME_HOOKS, False)

        if self.volume_hook == volume_hook:
            return

        self.volume_hook = volume_hook

        if self.volume_hook:
            _LOGGER.error("Enable hook %s", self.volume_hook)

        else:
            _LOGGER.error("Disable hook %s", self.volume_hook)

    @property
    def zones(self):
        """Return list of zones."""
        return self.roonapi.zones

    def add_player_id(self, entity_id, roon_name):
        """Register a roon player."""
        self._roon_name_by_id[entity_id] = roon_name
        self._id_by_roon_name[roon_name] = entity_id

    def add_player_volume_hook(self, entity_id, roon_name):
        """Register a volume controller for this player in roon."""
        if not self.volume_hook:
            return

        self.roonapi.register_volume_control(
            entity_id,
            roon_name,
            self.roonapi_volume_callback,
            0,
            "incremental",
            0,
            0,
            0,
            False,
        )

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
        """Callbacks from the roon api websocket with state change."""
        self.hass.add_job(self.async_update_changed_players(changed_zones))

    def roonapi_volume_callback(self, control_key, event, value):
        """Callbacks from the roon api websocket with volume request."""

        if event != "set_volume":
            _LOGGER.info("Received unsupported roon volume event %s", event)
            return

        if value > 0:
            roon_event = ROON_EVENT_VOLUME_UP
        else:
            roon_event = ROON_EVENT_VOLUME_DOWN

        event_data = {
            "entity_id": control_key,
            "type": roon_event,
        }
        _LOGGER.error("Publishing Roon Event %s", event_data)
        self.hass.bus.async_fire(ROON_EVENT, event_data)

    async def async_do_loop(self):
        """Background work loop."""
        self._exit = False
        await asyncio.sleep(INITIAL_SYNC_INTERVAL)
        while not self._exit:
            await self.async_update_players()
            await asyncio.sleep(FULL_SYNC_INTERVAL)

    async def async_update_changed_players(self, changed_zones_ids):
        """Update the players which were reported as changed by the Roon API."""
        _LOGGER.debug("async_update_changed_players %s", changed_zones_ids)
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
        _LOGGER.debug("async_update_players %s", zone_ids)
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
