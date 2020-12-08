"""MusicCast Device."""

from typing import Dict

from pyamaha import AsyncDevice, System, Zone


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


class MusicCastZoneData:
    """Object that holds data for a MusicCast device zone."""

    def __init__(self):
        """Ctor."""
        self.power = None
        self.min_volume = 0
        self.max_volume = 100
        self.current_volume = 0
        self.mute: bool = False
        self.input = None


class MusicCastDevice:
    """Dummy MusicCastDevice (device for HA) for Hello World example."""

    def __init__(self, client, ip):
        """Init dummy MusicCastDevice."""
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

        for callback in self._callbacks:
            callback()

    def register_callback(self, callback):
        """Register callback, called when MusicCastDevice changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

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

                self.data.zones[zone_id] = zone_data

        zones = {
            zone: await (await self.device.request(Zone.get_status(zone))).json()
            for zone in self._zone_ids
        }

        for zone_id in zones:
            zone = zones[zone_id]
            zone_data: MusicCastZoneData = self.data.zones.get(
                zone_id, MusicCastZoneData()
            )

            zone_data.power = zone.get("power")
            zone_data.current_volume = zone.get("volume")
            zone_data.mute = zone.get("mute")
            zone_data.input = zone.get("input")

            self.data.zones[zone_id] = zone_data
