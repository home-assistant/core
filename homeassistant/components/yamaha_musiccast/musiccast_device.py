"""MusicCast Device."""

import asyncio
from typing import Dict

from homeassistant.util import dt
from pyamaha import AsyncDevice, NetUSB, System, Zone


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
        self.data = MusicCastData()

        # the following data must not be updated frequently
        self._zone_ids = None
        self._network_status = None
        self._device_info = None
        self._features = None
        self._netusb_play_info = None

        print(f"HANDLE UDP ON {self.device._udp_port}")

    def handle(self, message):
        """Handle udp events."""
        # update data...

        print()
        print("=== INCOMING UDP EVENT FROM MUSICCAST ===")
        print(message)
        print("=========================================")
        print()

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
        print("Fetching netusb...")
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

    async def _fetch_zone(self, zone_id):
        print(f"Fetching zone {zone_id}...")
        zone = await (await self.device.request(Zone.get_status(zone_id))).json()
        zone_data: MusicCastZoneData = self.data.zones.get(zone_id, MusicCastZoneData())

        zone_data.power = zone.get("power")
        zone_data.current_volume = zone.get("volume")
        zone_data.mute = zone.get("mute")
        zone_data.input = zone.get("input")
        zone_data.sound_program = zone.get("sound_program")

        self.data.zones[zone_id] = zone_data

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

        await self._fetch_netusb()

        for zone in self._zone_ids:
            await self._fetch_zone(zone)
