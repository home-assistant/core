"""Harmony data object which contains the Harmony Client."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging

from aioharmony.const import ClientCallbackType, SendCommandDevice
import aioharmony.exceptions as aioexc
from aioharmony.harmonyapi import HarmonyAPI as HarmonyClient

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo

from .const import ACTIVITY_POWER_OFF
from .subscriber import HarmonySubscriberMixin

_LOGGER = logging.getLogger(__name__)


class HarmonyData(HarmonySubscriberMixin):
    """HarmonyData registers for Harmony hub updates."""

    def __init__(self, hass, address: str, name: str, unique_id: str):
        """Initialize a data object."""
        super().__init__(hass)
        self._name = name
        self._unique_id = unique_id
        self._available = False
        self._client = None
        self._address = address

    @property
    def activities(self):
        """List of all non-poweroff activity objects."""
        activity_infos = self._client.config.get("activity", [])
        return [
            info
            for info in activity_infos
            if info["label"] is not None and info["label"] != ACTIVITY_POWER_OFF
        ]

    @property
    def activity_names(self):
        """Names of all the remotes activities."""
        activity_infos = self.activities
        activities = [activity["label"] for activity in activity_infos]

        return activities

    @property
    def device_names(self):
        """Names of all of the devices connected to the hub."""
        device_infos = self._client.config.get("device", [])
        devices = [device["label"] for device in device_infos]

        return devices

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def unique_id(self):
        """Return the Harmony device's unique_id."""
        return self._unique_id

    @property
    def json_config(self):
        """Return the hub config as json."""
        if self._client.config is None:
            return None
        return self._client.json_config

    @property
    def available(self) -> bool:
        """Return if connected to the hub."""
        return self._available

    @property
    def current_activity(self) -> tuple:
        """Return the current activity tuple."""
        return self._client.current_activity

    def device_info(self, domain: str) -> DeviceInfo:
        """Return hub device info."""
        model = "Harmony Hub"
        if "ethernetStatus" in self._client.hub_config.info:
            model = "Harmony Hub Pro 2400"
        return DeviceInfo(
            identifiers={(domain, self.unique_id)},
            manufacturer="Logitech",
            model=model,
            name=self.name,
            sw_version=self._client.hub_config.info.get(
                "hubSwVersion", self._client.fw_version
            ),
            configuration_url="https://www.logitech.com/en-us/my-account",
        )

    async def connect(self) -> bool:
        """Connect to the Harmony Hub."""
        _LOGGER.debug("%s: Connecting", self._name)

        callbacks = {
            "config_updated": self._config_updated,
            "connect": self._connected,
            "disconnect": self._disconnected,
            "new_activity_starting": self._activity_starting,
            "new_activity": self._activity_started,
        }
        self._client = HarmonyClient(
            ip_address=self._address, callbacks=ClientCallbackType(**callbacks)
        )

        connected = False
        try:
            connected = await self._client.connect()
        except (asyncio.TimeoutError, aioexc.TimeOut) as err:
            await self._client.close()
            raise ConfigEntryNotReady(
                f"{self._name}: Connection timed-out to {self._address}:8088"
            ) from err
        except (ValueError, AttributeError) as err:
            await self._client.close()
            raise ConfigEntryNotReady(
                f"{self._name}: Error {err} while connected HUB at: {self._address}:8088"
            ) from err
        if not connected:
            await self._client.close()
            raise ConfigEntryNotReady(
                f"{self._name}: Unable to connect to HUB at: {self._address}:8088"
            )

    async def shutdown(self):
        """Close connection on shutdown."""
        _LOGGER.debug("%s: Closing Harmony Hub", self._name)
        try:
            await self._client.close()
        except aioexc.TimeOut:
            _LOGGER.warning("%s: Disconnect timed-out", self._name)

    async def async_start_activity(self, activity: str):
        """Start an activity from the Harmony device."""

        if not activity:
            _LOGGER.error("%s: No activity specified with turn_on service", self.name)
            return

        activity_id = None
        activity_name = None

        if activity.isdigit() or activity == "-1":
            _LOGGER.debug("%s: Activity is numeric", self.name)
            activity_name = self._client.get_activity_name(int(activity))
            if activity_name:
                activity_id = activity

        if activity_id is None:
            _LOGGER.debug("%s: Find activity ID based on name", self.name)
            activity_name = str(activity)
            activity_id = self._client.get_activity_id(activity_name)

        if activity_id is None:
            _LOGGER.error("%s: Activity %s is invalid", self.name, activity)
            return

        _, current_activity_name = self.current_activity
        if current_activity_name == activity_name:
            # Automations or HomeKit may turn the device on multiple times
            # when the current activity is already active which will cause
            # harmony to loose state.  This behavior is unexpected as turning
            # the device on when its already on isn't expected to reset state.
            _LOGGER.debug(
                "%s: Current activity is already %s", self.name, activity_name
            )
            return

        await self.async_lock_start_activity()
        try:
            await self._client.start_activity(activity_id)
        except aioexc.TimeOut:
            _LOGGER.error("%s: Starting activity %s timed-out", self.name, activity)
            self.async_unlock_start_activity()

    async def async_power_off(self):
        """Start the PowerOff activity."""
        _LOGGER.debug("%s: Turn Off", self.name)
        try:
            await self._client.power_off()
        except aioexc.TimeOut:
            _LOGGER.error("%s: Powering off timed-out", self.name)

    async def async_send_command(
        self,
        commands: Iterable[str],
        device: str,
        num_repeats: int,
        delay_secs: float,
        hold_secs: float,
    ):
        """Send a list of commands to one device."""
        device_id = None
        if device.isdigit():
            _LOGGER.debug("%s: Device %s is numeric", self.name, device)
            if self._client.get_device_name(int(device)):
                device_id = device

        if device_id is None:
            _LOGGER.debug(
                "%s: Find device ID %s based on device name", self.name, device
            )
            device_id = self._client.get_device_id(str(device).strip())

        if device_id is None:
            _LOGGER.error("%s: Device %s is invalid", self.name, device)
            return

        _LOGGER.debug(
            "Sending commands to device %s holding for %s seconds "
            "with a delay of %s seconds",
            device,
            hold_secs,
            delay_secs,
        )

        # Creating list of commands to send.
        snd_cmnd_list = []
        for _ in range(num_repeats):
            for single_command in commands:
                send_command = SendCommandDevice(
                    device=device_id, command=single_command, delay=hold_secs
                )
                snd_cmnd_list.append(send_command)
                if delay_secs > 0:
                    snd_cmnd_list.append(float(delay_secs))

        _LOGGER.debug("%s: Sending commands", self.name)
        try:
            result_list = await self._client.send_commands(snd_cmnd_list)
        except aioexc.TimeOut:
            _LOGGER.error("%s: Sending commands timed-out", self.name)
            return

        for result in result_list:
            _LOGGER.error(
                "Sending command %s to device %s failed with code %s: %s",
                result.command.command,
                result.command.device,
                result.code,
                result.msg,
            )

    async def change_channel(self, channel: int):
        """Change the channel using Harmony remote."""
        _LOGGER.debug("%s: Changing channel to %s", self.name, channel)
        try:
            await self._client.change_channel(channel)
        except aioexc.TimeOut:
            _LOGGER.error("%s: Changing channel to %s timed-out", self.name, channel)

    async def sync(self) -> bool:
        """Sync the Harmony device with the web service.

        Returns True if the sync was successful.
        """
        _LOGGER.debug("%s: Syncing hub with Harmony cloud", self.name)
        try:
            await self._client.sync()
        except aioexc.TimeOut:
            _LOGGER.error("%s: Syncing hub with Harmony cloud timed-out", self.name)
            return False
        else:
            return True
