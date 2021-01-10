"""MusicCast Device."""

import asyncio
import logging
from typing import Dict

from pyamaha import AsyncDevice, Dist, NetUSB, System, Tuner, Zone

from homeassistant.components.yamaha_musiccast.const import ATTR_MC_LINK_SOURCES, NULL_GROUP, ATTR_MC_LINK, DOMAIN
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)


class MusicCastGroupException(Exception):
    pass

class MusicCastData:
    """Object that holds data for a MusicCast device."""

    def __init__(self):
        """Ctor."""
        # device info
        self.model_name = None
        self.system_version = None

        # network status
        self.mac_addresses = None
        self.network_name = None

        # features
        self.zones: Dict[str, MusicCastZoneData] = {}
        self.input_names: Dict[str, str] = {}

        # NetUSB data
        self.netusb_input = None
        self.netusb_playback = None
        self.netusb_repeat = None
        self.netusb_shuffle = None
        self.netusb_artist = None
        self.netusb_album = None
        self.netusb_track = None
        self.netusb_albumart_url = None
        self.netusb_play_time = None
        self.netusb_play_time_updated = None
        self.netusb_total_time = None

        # Tuner
        self.band = None
        self._am_freq = 1
        self._fm_freq = 1
        self.rds_text_a = ""
        self.rds_text_b = ""

        self.dab_service_label = ""
        self.dab_dls = ""

        self.last_group_role = None
        self.last_group_id = None
        self.group_id = None
        self.group_name = None
        self.group_role = None
        self.group_server_zone = None
        self.group_client_list = []
        self.group_update_lock = asyncio.locks.Lock()

    @property
    def fm_freq(self):
        """Return a formatted string with fm frequency."""
        return "FM {:.2f} MHz".format(self._fm_freq / 1000)

    @property
    def am_freq(self):
        """Return a formatted string with am frequency."""
        return f"AM {self._am_freq:.2f} KHz"


class MusicCastZoneData:
    """Object that holds data for a MusicCast device zone."""

    def __init__(self):
        """Ctor."""
        self.power = None
        self.min_volume = 0
        self.max_volume = 100
        self.current_volume = 0
        self.mute: bool = False
        self.input_list = []
        self.input = None
        self.sound_program_list = []
        self.sound_program = None


class MusicCastDevice:
    """Dummy MusicCastDevice (device for HA) for Hello World example."""

    def __init__(self, hass, client, ip):
        """Init dummy MusicCastDevice."""
        self.hass = hass
        self.client = client
        self.ip = ip
        self.device = AsyncDevice(client, ip, self.handle)
        self._callbacks = set()
        self._group_update_callbacks = set()
        self.data = MusicCastData()
        self.group_master_id = len(self.hass.data.get(DOMAIN, {}).values())

        # the following data must not be updated frequently
        self._zone_ids = None
        self._network_status = None
        self._device_info = None
        self._features = None
        self._netusb_play_info = None
        self._tuner_play_info = None
        self._distribution_info = {None}
        self._name_text = None

        print(f"HANDLE UDP ON {self.device._udp_port}")

    def handle(self, message):
        """Handle udp events."""
        # update data...

        # print()
        # print("=== INCOMING UDP EVENT FROM MUSICCAST ===")
        # print(message)
        # print("=========================================")
        # print()

        for parameter in message:
            if parameter in ["main", "zone2", "zone3", "zone4"]:
                new_zone_data = message[parameter]

                self.data.zones[parameter].current_volume = new_zone_data.get(
                    "volume", self.data.zones[parameter].current_volume
                )
                self.data.zones[parameter].power = new_zone_data.get(
                    "power", self.data.zones[parameter].power
                )
                self.data.zones[parameter].mute = new_zone_data.get(
                    "mute", self.data.zones[parameter].mute
                )
                self.data.zones[parameter].input = new_zone_data.get(
                    "input", self.data.zones[parameter].input
                )

                if new_zone_data.get("play_info_updated") or new_zone_data.get(
                    "status_updated"
                ):
                    asyncio.run_coroutine_threadsafe(
                        self._fetch_zone(parameter), self.hass.loop
                    ).result()

        if "netusb" in message.keys():
            if message.get("netusb").get("play_info_updated"):
                asyncio.run_coroutine_threadsafe(
                    self._fetch_netusb(), self.hass.loop
                ).result()

            play_time = message.get("netusb").get("play_time")
            if play_time:
                self.data.netusb_play_time = play_time
                self.data.netusb_play_time_updated = dt.utcnow()

        if "tuner" in message.keys():
            if message.get("tuner").get("play_info_updated"):
                asyncio.run_coroutine_threadsafe(
                    self._fetch_tuner(), self.hass.loop
                ).result()

        if "dist" in message.keys():
            if message.get("dist").get("dist_info_updated"):
                asyncio.run_coroutine_threadsafe(
                    self._fetch_distribution_data(), self.hass.loop
                ).result()

        for callback in self._callbacks:
            callback()

    def register_callback(self, callback):
        """Register callback, called when MusicCastDevice changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    async def _fetch_netusb(self):
        """Fetch NetUSB data."""
        _LOGGER.debug("Fetching netusb...")
        self._netusb_play_info = await (
            await self.device.request(NetUSB.get_play_info())
        ).json()

        self.data.netusb_input = self._netusb_play_info.get(
            "input", self.data.netusb_input
        )
        self.data.netusb_playback = self._netusb_play_info.get(
            "playback", self.data.netusb_playback
        )
        self.data.netusb_repeat = self._netusb_play_info.get(
            "repeat", self.data.netusb_repeat
        )
        self.data.netusb_shuffle = self._netusb_play_info.get(
            "shuffle", self.data.netusb_shuffle
        )
        self.data.netusb_artist = self._netusb_play_info.get(
            "artist", self.data.netusb_artist
        )
        self.data.netusb_album = self._netusb_play_info.get(
            "album", self.data.netusb_album
        )
        self.data.netusb_track = self._netusb_play_info.get(
            "track", self.data.netusb_track
        )
        self.data.netusb_albumart_url = self._netusb_play_info.get(
            "albumart_url", self.data.netusb_albumart_url
        )
        self.data.netusb_total_time = self._netusb_play_info.get("total_time", None)
        self.data.netusb_play_time = self._netusb_play_info.get("play_time", None)

        self.data.netusb_play_time_updated = dt.utcnow()

    async def _fetch_tuner(self):
        """Fetch tuner data."""
        _LOGGER.debug("Fetching tuner...")
        self._tuner_play_info = await (
            await self.device.request(Tuner.get_play_info())
        ).json()

        self.data.band = self._tuner_play_info.get("band", self.data.band)

        self.data._fm_freq = self._tuner_play_info.get("fm", {}).get(
            "freq", self.data._fm_freq
        )
        self.data._am_freq = self._tuner_play_info.get("am", {}).get(
            "freq", self.data._am_freq
        )
        self.data.rds_text_a = (
            self._tuner_play_info.get("rds", {})
            .get("radio_text_a", self.data.rds_text_a)
            .strip()
        )
        self.data.rds_text_b = (
            self._tuner_play_info.get("rds", {})
            .get("radio_text_b", self.data.rds_text_b)
            .strip()
        )
        self.data.dab_service_label = (
            self._tuner_play_info.get("dab", {})
            .get("service_label", self.data.dab_service_label)
            .strip()
        )
        self.data.dab_dls = (
            self._tuner_play_info.get("dab", {}).get("dls", self.data.dab_dls).strip()
        )

    async def _fetch_zone(self, zone_id):
        _LOGGER.debug(f"Fetching zone {zone_id}...")
        zone = await (await self.device.request(Zone.get_status(zone_id))).json()
        zone_data: MusicCastZoneData = self.data.zones.get(zone_id, MusicCastZoneData())

        zone_data.power = zone.get("power")
        zone_data.current_volume = zone.get("volume")
        zone_data.mute = zone.get("mute")
        zone_data.input = zone.get("input")
        zone_data.sound_program = zone.get("sound_program")

        self.data.zones[zone_id] = zone_data

    async def _fetch_distribution_data(self):
        _LOGGER.debug(f"Fetching Distribution data...")
        self._distribution_info = await (
            await self.device.get(Dist.get_distribution_info())
        ).json()
        self.data.last_group_role = self.data.group_role
        self.data.last_group_id = self.data.group_id
        self.data.group_id = self._distribution_info.get("group_id", None)
        self.data.group_name = self._distribution_info.get("group_name", None)
        self.data.group_role = self._distribution_info.get("role", None)
        self.data.group_server_zone = self._distribution_info.get("server_zone", None)
        self.data.group_client_list = [
            client.get("ip_address", "")
            for client in self._distribution_info.get("client_list", [])
        ]
        if not self.data.group_update_lock.locked():
            for cb in self._group_update_callbacks:
                await cb()

    async def fetch(self):
        """Fetch data from musiccast device."""
        if not self._network_status:
            self._network_status = await (
                await self.device.request(System.get_network_status())
            ).json()

            self.data.network_name = self._network_status.get("network_name")
            self.data.mac_addresses = self._network_status.get("mac_address")

        if not self._device_info:
            self._device_info = await (
                await self.device.request(System.get_device_info())
            ).json()

            self.data.model_name = self._device_info.get("model_name")
            self.data.system_version = self._device_info.get("system_version")

        if not self._features:
            self._features = await (
                await self.device.request(System.get_features())
            ).json()

            self._zone_ids = [zone.get("id") for zone in self._features.get("zone", [])]

            for zone in self._features.get("zone", []):
                zone_id = zone.get("id")

                zone_data: MusicCastZoneData = self.data.zones.get(
                    zone_id, MusicCastZoneData()
                )

                range_volume = next(
                    item for item in zone.get("range_step") if item["id"] == "volume"
                )

                zone_data.min_volume = range_volume.get("min")
                zone_data.max_volume = range_volume.get("max")

                zone_data.sound_program_list = zone.get("sound_program_list", [])
                zone_data.input_list = zone.get("input_list", [])

                self.data.zones[zone_id] = zone_data

        self._name_text = await (
            await self.device.request(System.get_name_text(None))
        ).json()

        self.data.input_names = {
            input.get("id"): input.get("text")
            for input in self._name_text.get("input_list")
        }

        await self._fetch_netusb()
        await self._fetch_tuner()
        await self._fetch_distribution_data()

        for zone in self._zone_ids:
            await self._fetch_zone(zone)

    def register_group_update_callback(self, callback):
        """Register async methods called after changes of the distribution data here."""
        self._group_update_callbacks.add(callback)

    # Simple check functions for better code readability

    def _check_clients_removed(self, clients):
        return all([client not in self.data.group_client_list for client in clients])

    def _check_clients_added(self, clients):
        return all([client in self.data.group_client_list for client in clients])

    def _check_group_id(self, group_id):
        return self.data.group_id == group_id

    def _check_source(self, source, zone):
        return self.data.zones[zone].input == source

    def _check_group_role(self, role):
        return self.data.group_role == role

    def _check_group_server_zone(self, zone):
        return self.data.group_server_zone == zone

    # Group update checking functions

    async def wait_for_data_update(self, checks):
        while True:
            if all([check() for check in checks]):
                return
            await asyncio.sleep(0.1)

    async def check_group_data(self, checks):
        try:
            await asyncio.wait_for(self.wait_for_data_update(checks), 1)
        except asyncio.exceptions.TimeoutError:
            _LOGGER.warning("Coordinator of " + self.ip + " did not receive the expected group data update via UDP. "
                                                          "Fetching manually.")
            await self._fetch_distribution_data()
        return all([check() for check in checks])

    # Group server functions

    async def mc_server_group_extend(self, zone, client_ips, group_id, retry=True):
        """Extend the given group by the given clients.

        If the group does not exist, it will be created.
        """
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(
                    group_id, zone, "add", client_ips
                )
            )
            await self.device.get(Dist.start_distribution(self.group_master_id))
            if await self.check_group_data([lambda: self._check_clients_added(client_ips),
                                            lambda: self._check_group_id(group_id),
                                            lambda: self._check_group_role("server"),
                                            lambda: self._check_group_server_zone(zone)]):
                return

        if retry:
            await self.mc_server_group_extend(zone, client_ips, group_id, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to extent group by clients " + str(client_ips))

    async def mc_server_group_reduce(self, zone, client_ips_for_removal, retry=True):
        """Reduce the current group by the given clients."""
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(
                    self.data.group_id,
                    zone,
                    "remove",
                    client_ips_for_removal,
                )
            )
            if len(self.data.group_client_list):
                await self.device.get(Dist.start_distribution(self.group_master_id))
            if await self.check_group_data([lambda: self._check_clients_removed(client_ips_for_removal)]):
                return

        if retry:
            await self.mc_server_group_reduce(zone, client_ips_for_removal, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to reduce group by clients " +
                                          str(client_ips_for_removal))

    async def mc_server_group_close(self, retry=True):
        """Close the current group."""
        async with self.data.group_update_lock:
            await self.device.get(Dist.stop_distribution())
            await self.device.post(
                *Dist.set_server_info("")
            )
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_server_group_close(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to close group.")

    # Group client functions

    async def mc_client_join(self, server_ip, group_id, zone, retry=True):
        """Join the given group as a client."""
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_client_info(group_id, zone, server_ip)
            )
            await self.device.request(
                Zone.set_input(zone, ATTR_MC_LINK, "")
            )
            if await self.check_group_data([lambda: self._check_group_id(group_id),
                                            lambda: self._check_group_role("client"),
                                            lambda: self._check_source(ATTR_MC_LINK, zone)]):
                return

        if retry:
            await self.mc_client_join(server_ip, group_id, zone, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to join the group.")

    async def mc_client_unjoin(self, retry=True):
        """Unjoin the current group."""
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_client_info("")
            )
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_client_unjoin(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to leave group")

    # Misc

    def get_save_inputs(self, zone_id):
        """Return a save save source for the given zone_id.

        A save input can be any input except netusb ones if the netusb module is already in use."""
        netusb_in_use = any([zone.input == self.data.netusb_input for zone in self.data.zones.values()])
        return [input.get('id') for input in self._features.get('system', {}).get('input_list', [])
                if input.get('distribution_enable') and
                (input.get('play_info_type') != 'netusb' or not netusb_in_use) and
                input.get('id') not in ATTR_MC_LINK_SOURCES and
                input.get('id') in self.data.zones.get(zone_id).input_list]
